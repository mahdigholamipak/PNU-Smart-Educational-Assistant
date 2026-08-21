"""RAG orchestration: OCR -> query rewrite -> embedding -> retrieval -> generation.

Implements the "Hybrid Expert Pedagogical RAG" approach where the LLM acts as
an expert professor, solving problems step-by-step rather than strictly saying
"not found in context." The system prompts are kept here (they are the
product's core behavior) but the error kinds are now an enum and the return
value is a typed :class:`RAGResult` instead of a bare 4-tuple.
"""

import hashlib
import logging
from dataclasses import dataclass, field
from enum import Enum

from sqlalchemy.orm import Session

from app.config import settings
from app.models import Resource
from app.services.cache import LRUCache
from app.services.chat_manager import generate_chat_response
from app.services.conversation_memory import build_gemini_history, rewrite_search_query
from app.services.embedding_manager import embed_query_cached, key_manager
from app.services.llm_service import (
    resolve_api_keys,
    resolve_chat_model,
    resolve_embedding_model,
    resolve_ocr_model,
)
from app.services.vector_store import search_course_documents_embedded

logger = logging.getLogger(__name__)

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

# Lightweight OCR prompt: extract raw text from the attached image with no
# commentary, so the combined query can drive the ChromaDB vector search.
# Kept dense and imperative to minimize token cost while preserving the two
# rules that matter most: raw output and LaTeX isolation of mixed-direction
# expressions (which the RTL KaTeX renderer depends on).
OCR_SYSTEM_PROMPT = """Extract all Persian/English text and equations from this image.

<rules>
1. Output ONLY the extracted text — no prefixes, explanations, or quotes.
2. No readable text → output nothing.
3. English variables/numbers mixed with Persian (e.g. A[6], B[1], C[4]) MUST be
   wrapped in inline LaTeX ($A[6]$, $B[1]$, $C[4]$) for correct RTL isolation.
</rules>
"""

# LRU cache for OCR results, keyed by SHA-256 of the raw image bytes. The same
# screenshot (e.g. a question image pasted once or shared between users) is
# only sent to Gemini once, eliminating redundant OCR token spend.
_ocr_cache = LRUCache[str](max_size=settings.ocr_cache_size)


class RAGErrorKind(str, Enum):
    """Typed error kinds returned by the RAG pipeline."""

    NONE = "none"
    NO_RESOURCES = "no_resources"
    BROKEN_RESOURCES = "broken_resources"
    AI_CONNECTION = "ai_connection"


@dataclass
class RAGResult:
    """Typed result of the RAG pipeline.

    ``answer`` is the generated text (may be empty on error).
    ``sources`` is the list of citation sources (may be empty).
    ``error_kind`` is one of :class:`RAGErrorKind`.
    ``error_detail`` carries the underlying exception message for logging.
    """

    answer: str = ""
    sources: list[dict] = field(default_factory=list)
    error_kind: RAGErrorKind = RAGErrorKind.NONE
    error_detail: str | None = None

    @property
    def ok(self) -> bool:
        """True when the pipeline produced a usable answer."""
        return self.error_kind == RAGErrorKind.NONE


def _check_course_resources(course_id: int, db: Session) -> RAGErrorKind | None:
    """Return an error kind if the course has no usable (ready) resources, else None."""
    resources = db.query(Resource).filter(Resource.course_id == course_id).all()
    ready = [r for r in resources if r.status == "ready"]
    if not ready:
        # If there are resources but none are ready, they're broken/failed.
        if resources:
            return RAGErrorKind.BROKEN_RESOURCES
        return RAGErrorKind.NO_RESOURCES
    return None


def extract_image_text(image_data: str) -> str:
    """Best-effort OCR: extract readable text from an attached image.

    Uses a fast Gemini-Flash call with the image attached. Results are cached
    by SHA-256 of the image bytes so the same screenshot is only sent to
    Gemini once. Any failure returns an empty string so the RAG pipeline
    gracefully falls back to the existing text-only search path — field
    extraction NEVER breaks the chat.
    """
    if not image_data:
        return ""

    # The data URL includes a "data:<mime>;base64," prefix — only hash the raw
    # base64 payload so identical images with different MIME labels share a key.
    b64_payload = image_data.split(",", 1)[1] if "," in image_data else image_data
    cache_key = hashlib.sha256(b64_payload.encode("utf-8")).hexdigest()

    if settings.cache_enabled:
        cached = _ocr_cache.get(cache_key)
        if cached is not None:
            return cached

    try:
        messages = [("user", "متن داخل تصویر را استخراج کن.", image_data)]
        extracted = generate_chat_response(messages, resolve_ocr_model(), system_prompt=OCR_SYSTEM_PROMPT)
        result = extracted.strip()
        if settings.cache_enabled:
            _ocr_cache.put(cache_key, result)
        return result
    except Exception as exc:
        logger.warning("OCR extraction failed (falling back to text-only): %s", exc)
        return ""


def _build_ai_answer(
    question: str,
    retrieved: list[dict],
    history: list[dict] | None = None,
    image_data: str | None = None,
    image_text: str = "",
) -> tuple[str, RAGErrorKind, str]:
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
        return answer, RAGErrorKind.NONE, ""
    except Exception as exc:
        logger.exception("AI answer generation failed: %s", exc)
        return "", RAGErrorKind.AI_CONNECTION, str(exc)


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
) -> RAGResult:
    """Generate a memory-aware RAG answer.

    Returns a :class:`RAGResult` with ``answer``, ``sources``, ``error_kind``
    and ``error_detail``.

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
    if resource_kind == RAGErrorKind.NO_RESOURCES:
        return RAGResult(
            answer="در حال حاضر هیچ منبع درسی برای این درس در سیستم بارگذاری نشده است. "
            "لطفاً از مدیر منابع بخواهید منابع درس را اضافه کند.",
            error_kind=RAGErrorKind.NO_RESOURCES,
        )
    if resource_kind == RAGErrorKind.BROKEN_RESOURCES:
        return RAGResult(
            answer="منابع درسی این درس دچار مشکل شده‌اند و در حال حاضر قابل استفاده نیستند. "
            "لطفاً با مدیر سیستم تماس بگیرید تا منابع بررسی و مجدداً بارگذاری شوند.",
            error_kind=RAGErrorKind.BROKEN_RESOURCES,
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
    #    Uses the LRU-cached + single-flight-coalesced path so repeated or
    #    concurrent identical queries never burn extra tokens.
    query_embedding = embed_query_cached(search_query, resolve_embedding_model())

    # 4. VECTOR SEARCH: query ChromaDB with the pre-computed embedding.
    retrieved = search_course_documents_embedded(
        course_id=course_id,
        query_embedding=query_embedding,
        top_k=5,
    )

    # 4b. Safety net: if the rewritten query returned nothing, retry with the
    #     original (combined) question text.
    if not retrieved and search_query != search_text:
        fallback_embedding = embed_query_cached(search_text, resolve_embedding_model())
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
        if ai_kind == RAGErrorKind.AI_CONNECTION:
            return RAGResult(
                answer="متأسفانه در ارتباط با مدل هوش مصنوعی خطایی رخ داد. "
                "لطفاً بعداً دوباره تلاش کنید یا با مدیر سیستم تماس بگیرید.",
                error_kind=RAGErrorKind.AI_CONNECTION,
                error_detail=ai_error,
            )

        return RAGResult(answer=answer)

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
    if ai_kind == RAGErrorKind.AI_CONNECTION:
        return RAGResult(
            answer="متأسفانه در ارتباط با مدل هوش مصنوعی خطایی رخ داد. "
            "لطفاً بعداً دوباره تلاش کنید یا با مدیر سیستم تماس بگیرید.",
            sources=sources,
            error_kind=RAGErrorKind.AI_CONNECTION,
            error_detail=ai_error,
        )

    return RAGResult(answer=answer, sources=sources)