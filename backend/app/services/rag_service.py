from sqlalchemy.orm import Session

from app.models import Resource
from app.services.chat_manager import generate_chat_response
from app.services.conversation_memory import build_gemini_history, rewrite_search_query
from app.services.embedding_manager import embed_batch_managed, key_manager
from app.services.llm_service import (
    resolve_api_keys,
    resolve_chat_model,
    resolve_embedding_model,
    resolve_ocr_model,
)
from app.services.vector_store import search_course_documents_embedded

SYSTEM_PROMPT = """You are an expert University Professor and Teaching Assistant. Your task is to provide accurate, step-by-step solutions to the student's queries based on your knowledge and the provided context.

<rules>
1. ACCURACY & LOGIC: Solve the problem step-by-step. If it is a multiple-choice question, explicitly state the final correct answer in Persian (e.g., "بنابراین، گزینه ۲ صحیح است").
2. IGNORE ARTIFACTS: Completely ignore booklet serial numbers (e.g., 1010, 1011) that may be printed repeatedly next to choices in the OCR text.
3. MATH & VARIABLES FORMATTING (CRITICAL):
   - You MUST NOT use Markdown backticks (` or ```) for variables, expressions, or math.
   - For inline variables and numbers (e.g., A, x, 2), use inline LaTeX: $A$, $x$, $2$.
   - For block equations, use block LaTeX: $$Need = Maximum - Allocation$$.
   - Never use code blocks for mathematical operations.
4. CITATIONS: Use the provided document chunks to ground your answer. When you use information from a chunk, insert a citation using the system's required format [n], where n is the chunk number shown next to "متن‌های مرجع". DO NOT use citations to indicate a multiple-choice option (e.g., never write "Option [3]").
</rules>
"""

# Error kinds returned by the RAG pipeline
KIND_OK = "none"
KIND_NO_RESOURCES = "no_resources"
KIND_BROKEN_RESOURCES = "broken_resources"
KIND_AI_CONNECTION = "ai_connection"

# Lightweight OCR prompt: extract raw text from the attached image with no
# commentary, so the combined query can drive the ChromaDB vector search.
OCR_SYSTEM_PROMPT = """Extract all Persian/English text, equations, and questions from this image accurately.

Rules:
1. Output ONLY the extracted text — no prefixes, suffixes, explanations, or quotes.
2. If the image contains a question, math expression, or technical term, write it exactly as-is.
3. If there is no readable text in the image, return an empty output.
4. Whenever you write English variables, state names, numbers, or bracket notations
   mixed with Persian text (e.g., A[6], B[1], C[4]), you MUST wrap them in inline
   LaTeX (e.g., `$A[6]$`, `$B[1]$`, `$C[4]$`). This ensures correct Left-to-Right
   rendering via math block isolation.
"""


def _check_course_resources(course_id: int, db: Session) -> str | None:
    """Return an error kind if the course has no usable (ready) resources, else None."""
    resources = db.query(Resource).filter(Resource.course_id == course_id).all()
    ready = [r for r in resources if r.status == "ready"]
    if not ready:
        return KIND_NO_RESOURCES
    return None


def extract_image_text(image_data: str) -> str:
    """Best-effort OCR: extract readable text from an attached image.

    Uses a fast Gemini-Flash call with the image attached. Any failure returns
    an empty string so the RAG pipeline gracefully falls back to the existing
    text-only search path — field extraction NEVER breaks the chat.
    """
    if not image_data:
        return ""
    try:
        messages = [("user", "متن داخل تصویر را استخراج کن.", image_data)]
        extracted = generate_chat_response(messages, resolve_ocr_model(), system_prompt=OCR_SYSTEM_PROMPT)
        return extracted.strip()
    except Exception:
        return ""


def _build_ai_answer(
    question: str,
    retrieved: list[dict],
    history: list[dict] | None = None,
    image_data: str | None = None,
    image_text: str = "",
) -> tuple[str, str, str]:
    """Call Gemini with the RAG context. Returns (answer, error_kind, error_detail).

    ``history`` is a list of ``{"role", "content"}`` dicts from the database
    (oldest-first). It is converted to an alternating user/model window and
    prepended to the current question so Gemini remembers the conversation.

    ``image_data`` is an optional Base64 data URL of a screenshot attached to
    the *current* user message. It is attached only to the current turn as a
    Gemini ``inline_data`` part so the model can analyze the visual question.

    ``image_text`` is the OCR-extracted text from the attached image (may be
    empty when no image or OCR produced no output).
    """
    context_blocks = []
    for i, hit in enumerate(retrieved, start=1):
        context_blocks.append(f"[{i}] {hit['filename']}\n{hit['content']}")
    context = "\n\n".join(context_blocks)

    # Build the full user turn that includes the RAG context.
    # If no chunks were retrieved (e.g. image-only message with no text to
    # search), instruct the model to analyze the attached image directly.
    if context:
        rag_question = f"متن‌های مرجع:\n{context}"
        if question.strip():
            rag_question += f"\n\nسؤال دانشجو:\n{question}"
        else:
            rag_question += "\n\nسؤال دانشجو:\n(تصویر پیوست‌شده را تحلیل کن)"
    else:
        rag_question = (
            "هیچ متن مرجعی به‌طور مستقیم برای این سؤال بازیابی نشد. "
            "به‌عنوان استاد دانشگاه، سؤال دانشجو را به‌طور کامل و گام‌به‌گام حل کن "
            "و مفاهیم پاسخ را به مباحث مرتبط درس و منابع مرجع پیوند بده."
        )
        if question.strip():
            rag_question += f"\n\nسؤال دانشجو:\n{question}"

    # If OCR extracted text from an attached image, surface it clearly to the
    # model (the raw image is still attached as inline_data on the final turn).
    if image_text:
        rag_question += f"\n\nمتن استخراج‌شده از تصویر:\n{image_text}"

    # Build a clean alternating user/model history + current question. The
    # SYSTEM_PROMPT is sent natively via Gemini's systemInstruction field below,
    # NOT merged into a user turn — this lets Gemini's attention mechanism treat
    # the dialogue as real conversation instead of a giant instruction blob.
    history_turns = build_gemini_history(history or [], rag_question)

    # Gemini requires strictly alternating user↔model turns with no leading
    # model turn. build_gemini_history already merges consecutive same-role
    # messages and always ends on a user turn (the current message).
    messages = history_turns

    # The image (when present) must ride on the LAST user turn — the current
    # message — so the Vision model sees it alongside the question and RAG
    # context. Attaching it to an early history turn would make Gemini
    # associate the screenshot with stale conversation context.
    if messages:
        *prior_turns, (last_role, last_content) = messages
        if last_role == "user":
            messages = list(prior_turns) + [("user", last_content, image_data)]
        else:
            messages = messages + [("user", "(تصویر پیوست‌شده را تحلیل کن)", image_data)]
    else:
        messages = [("user", rag_question, image_data)]

    try:
        answer = generate_chat_response(
            messages,
            resolve_chat_model(),
            system_prompt=SYSTEM_PROMPT,
        )
        return answer, KIND_OK, ""
    except Exception as exc:
        return "", KIND_AI_CONNECTION, str(exc)


def _make_snippet(content: str, max_len: int = 200) -> str:
    """Return a trimmed excerpt of a chunk for display in the citation tooltip."""
    content = " ".join(content.split())
    if len(content) <= max_len:
        return content
    return content[:max_len].rstrip() + "…"


def generate_rag_answer(
    question: str,
    course_id: int,
    db: Session,
    history: list[dict] | None = None,
    image_data: str | None = None,
    image_text: str = "",
) -> tuple[str, list[dict], str, str | None]:
    """Generate a memory-aware RAG answer.

    Returns ``(answer, sources, error_kind, error_detail)``.

    ``history`` is the recent conversation (list of ``{role, content}`` dicts).
    When present it is used for:
    1. **Query rewriting** — the user's ambiguous follow-up is expanded into a
       standalone vector query *before* searching ChromaDB.
    2. **Generation memory** — the conversation turns are prepended to the
       Gemini chat window so the LLM remembers the ongoing discussion.

    ``image_data`` is an optional Base64 data URL of a screenshot attached to
    the current user message. When present, a fast OCR call extracts the text
    from the image and the combined text (user prompt + OCR text) drives the
    ChromaDB vector search — so screenshots of questions actually retrieve
    relevant chunks. The raw image is also passed to the final Gemini call.

    ``image_text`` is an optional pre-computed OCR result for the attached
    image. When provided, the internal OCR call is SKIPPED (avoids a duplicate
    Gemini call when the caller already extracted the text, e.g. for chat
    title generation). If empty and an image is present, OCR runs internally.
    """
    history = history or []

    # 0. CRITICAL: ensure the smart key pool is configured before any LLM call.
    #    Without this, generate_chat_response() raises "no API key configured"
    #    and the OCR + generation steps silently fail — making the whole RAG
    #    pipeline appear broken even though the code is correct.
    key_manager.configure(resolve_api_keys())

    # 1. Check course-level resource availability
    resource_kind = _check_course_resources(course_id, db)
    if resource_kind == KIND_NO_RESOURCES:
        return (
            "در حال حاضر هیچ منبع درسی برای این درس در سیستم بارگذاری نشده است. "
            "لطفاً از مدیر منابع بخواهید منابع درس را اضافه کند.",
            [],
            KIND_NO_RESOURCES,
            None,
        )
    if resource_kind == KIND_BROKEN_RESOURCES:
        return (
            "منابع درسی این درس دچار مشکل شده‌اند و در حال حاضر قابل استفاده نیستند. "
            "لطفاً با مدیر سیستم تماس بگیرید تا منابع بررسی و مجدداً بارگذاری شوند.",
            [],
            KIND_BROKEN_RESOURCES,
            None,
        )

    # 1b. PRE-RETRIEVAL OCR: if an image is attached, extract its text with a
    #     fast Gemini-Flash call so the vector search can use the screenshot's
    #     actual question content. Best-effort — any failure returns "" and the
    #     pipeline gracefully falls back to the text-only path.
    #     If the caller already supplied ``image_text`` (e.g. from chat title
    #     generation), reuse it and skip the duplicate OCR call.
    if not image_text and image_data:
        image_text = extract_image_text(image_data)

    # 2. Build the combined search text: user prompt + OCR-extracted image text.
    #    This is the CRITICAL fix — the vector DB now receives the screenshot's
    #    content instead of only the (possibly empty) typed text.
    combined_text = question.strip()
    if image_text:
        combined_text = f"{combined_text}\n{image_text}".strip() if combined_text else image_text

    # 2b. Rewrite the query using conversation context (CRITICAL for follow-ups).
    #     The rewritten/standalone query is used EXCLUSIVELY for ChromaDB search.
    #     For image-only messages (blank text), fall back to the last user text
    #     from history or a generic query so vector search still has something.
    search_text = combined_text
    if not search_text:
        for msg in reversed(history):
            if msg["role"] == "user" and msg["content"].strip():
                search_text = msg["content"].strip()
                break
        if not search_text:
            search_text = "سؤال امتحانی"

    search_query = rewrite_search_query(search_text, history)

    # 3. EMBEDDING: explicitly generate the vector for the (possibly combined)
    #    query using the same Gemini embedding model that indexed the chunks.
    #    This guarantees the exact embedding of the combined OCR+user text is
    #    used for retrieval — ChromaDB does NOT re-embed the query text.
    query_embedding = embed_batch_managed([search_query], resolve_embedding_model())[0]

    # 4. VECTOR SEARCH: query ChromaDB with the pre-computed embedding.
    retrieved = search_course_documents_embedded(
        course_id=course_id,
        query_embedding=query_embedding,
        top_k=5,
    )

    # 4b. Safety net: if the rewritten query returned nothing, retry with the
    #     original (combined) question text.
    if not retrieved and search_query != search_text:
        fallback_embedding = embed_batch_managed([search_text], resolve_embedding_model())[0]
        retrieved = search_course_documents_embedded(
            course_id=course_id,
            query_embedding=fallback_embedding,
            top_k=5,
        )

    # 4c. Zero-retrieval fallback: if no chunks matched (e.g. an exam question
    #     worded differently from the textbook), do NOT refuse. Still call Gemini
    #     with an empty context — the professor-mode system prompt answers from
    #     expertise and bridges the topic back to the course. The image (if any)
    #     is passed along so the model can analyze the visual question.
    if not retrieved:
        answer, ai_kind, ai_error = _build_ai_answer(
            question,
            [],
            history,
            image_data,
            image_text,
        )

        # If AI failed, return honest error + empty sources
        if ai_kind == KIND_AI_CONNECTION:
            return (
                "متأسفانه در ارتباط با مدل هوش مصنوعی خطایی رخ داد. "
                "لطفاً بعداً دوباره تلاش کنید یا با مدیر سیستم تماس بگیرید.",
                [],
                KIND_AI_CONNECTION,
                ai_error,
            )

        return answer, [], KIND_OK, None

    # 5. Build context + conversation history and call Gemini.
    #    The image (if any) is passed to the LLM along with the OCR-extracted
    #    text so the model can cross-reference the visual with the retrieval.
    answer, ai_kind, ai_error = _build_ai_answer(
        question,
        retrieved,
        history,
        image_data,
        image_text,
    )

    # 6. Build indexed source citations (1..n over ALL retrieved hits) so the
    #    model's [i] references map 1:1 to the numbered context blocks above.
    sources = []
    for i, hit in enumerate(retrieved, start=1):
        sources.append(
            {
                "id": i,
                "filename": hit["filename"],
                "page": hit.get("page"),
                "snippet": _make_snippet(hit["content"]),
                "resource_id": hit["resource_id"],
                "chunk_index": hit["chunk_index"],
                "score": hit["score"],
            }
        )

    # If AI failed but we have retrieval, still return honest error + sources
    if ai_kind == KIND_AI_CONNECTION:
        return (
            "متأسفانه در ارتباط با مدل هوش مصنوعی خطایی رخ داد. "
            "لطفاً بعداً دوباره تلاش کنید یا با مدیر سیستم تماس بگیرید.",
            sources,
            KIND_AI_CONNECTION,
            ai_error,
        )

    return answer, sources, KIND_OK, None