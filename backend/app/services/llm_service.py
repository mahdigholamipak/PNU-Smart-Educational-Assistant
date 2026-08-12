import os
from typing import Any

from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings

from app.config import settings
from app.database import SessionLocal
from app.models import Setting


def _resolve_api_key() -> str:
    """Resolve the Gemini API key from env or the settings table (admin-managed)."""
    env_key = settings.gemini_api_key or os.getenv("GEMINI_API_KEY", "")
    if env_key:
        return env_key

    db = SessionLocal()
    try:
        setting = db.query(Setting).filter(Setting.key == "gemini_api_key").first()
        return setting.value if setting and setting.value else ""
    finally:
        db.close()


def get_embedding_function() -> Any:
    """Return the Gemini embedding function used by ChromaDB."""
    return GoogleGenerativeAIEmbeddings(
        model=settings.gemini_embedding_model,
        google_api_key=_resolve_api_key(),
    )


def get_chat_model():
    """Return the Gemini chat model for RAG answer generation."""
    return ChatGoogleGenerativeAI(
        model=settings.gemini_chat_model,
        google_api_key=_resolve_api_key(),
        temperature=0.2,
    )