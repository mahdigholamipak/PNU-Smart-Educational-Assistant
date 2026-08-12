from sqlalchemy.orm import Session

from app.services.llm_service import get_chat_model
from app.services.vector_store import search_course_documents

SYSTEM_PROMPT = """تو یک دستیار آموزشی هوشمند برای دانشجویان هستی.
فقط و فقط بر اساس «متن‌های مرجع» زیر به سؤال دانشجو پاسخ بده.
اگر پاسخ سؤال در متن‌های مرجع وجود نداشت، صراحتاً بگو که در منابع درسی موجود نیست و هرگز حدس نزن یا اطلاعات خارج از منابع اضافه نکن.
پاسخ باید به زبان فارسی، دقیق، مختصر و مبتنی بر منابع باشد."""


def generate_rag_answer(question: str, course_id: int, db: Session) -> tuple[str, list[dict]]:
    """Generate a RAG-based answer using ChromaDB retrieval and Gemini generation."""
    # 1. Retrieve relevant chunks scoped to the course
    retrieved = search_course_documents(course_id=course_id, query=question, top_k=5)

    # 2. If no documents indexed, return an honest fallback
    if not retrieved:
        return (
            "در حال حاضر هیچ منبع درسی برای این درس در سیستم بارگذاری نشده است. "
            "لطفاً ابتدا از مدیر سیستم بخواهید منابع درس را اضافه کند.",
            [],
        )

    # 3. Build the context block with cited sources
    context_blocks = []
    for i, hit in enumerate(retrieved, start=1):
        context_blocks.append(f"[منبع {i}: {hit['filename']}]\n{hit['content']}")
    context = "\n\n".join(context_blocks)

    # 4. Build the prompt and call Gemini
    messages = [
        ("system", SYSTEM_PROMPT),
        ("human", f"متن‌های مرجع:\n{context}\n\nسؤال دانشجو:\n{question}"),
    ]

    try:
        model = get_chat_model()
        response = model.invoke(messages)
        answer = response.content if hasattr(response, "content") else str(response)
    except Exception as exc:
        answer = (
            "متأسفانه در ارتباط با مدل هوش مصنوعی خطایی رخ داد. "
            "لطفاً بعداً دوباره تلاش کنید. جزئیات خطا: "
            f"{exc}"
        )

    # 5. Build source citations (unique by filename)
    sources = []
    seen = set()
    for hit in retrieved:
        filename = hit["filename"]
        if filename not in seen:
            seen.add(filename)
            sources.append(
                {
                    "filename": filename,
                    "resource_id": hit["resource_id"],
                    "chunk_index": hit["chunk_index"],
                    "score": hit["score"],
                }
            )

    return answer, sources