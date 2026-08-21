"""Gemini model/key resolution and ChromaDB embedding-function adapter.

Responsibilities:
- Resolve the active Gemini API keys (settings table -> env/config fallback).
- Resolve the chat/rewrite/OCR/embedding model names (settings table -> config).
- Provide a ChromaDB-compatible embedding function that routes every real
  embedding call through the decoupled :mod:`embedding_manager` — never a raw
  LangChain client.

The settings-table reads are cached for a short TTL so repeated resolution
during a single request doesn't open a new DB session per call (the previous
behavior caused connection churn under load).
"""

import os
import threading
import time
from typing import Any

from chromadb.api.types import EmbeddingFunction, Embeddings

from app.config import settings
from app.database import SessionLocal
from app.models import Setting
from app.services.embedding_manager import embed_batch_managed, key_manager

#: TTL (seconds) for the cached settings-table reads.
_SETTINGS_CACHE_TTL = 5.0

_settings_cache: dict[str, tuple[float, str]] = {}
_settings_cache_lock = threading.Lock()


def _get_setting_value(key: str) -> str:
    """Read a setting value from the admin-managed settings table.

    Cached for ``_SETTINGS_CACHE_TTL`` seconds so repeated calls within a
    request (e.g. resolving chat + embedding + OCR models) don't each open a
    fresh DB session. The cache is invalidated naturally by the TTL, so admin
    edits propagate within a few seconds.
    """
    now = time.monotonic()
    with _settings_cache_lock:
        cached = _settings_cache.get(key)
        if cached and now - cached[0] < _SETTINGS_CACHE_TTL:
            return cached[1]

    db = SessionLocal()
    try:
        setting = db.query(Setting).filter(Setting.key == key).first()
        value = setting.value if setting and setting.value else ""
    finally:
        db.close()

    with _settings_cache_lock:
        _settings_cache[key] = (now, value)
    return value


def resolve_api_key() -> str:
    """Resolve a single Gemini API key (first available) for backward compatibility."""
    keys = resolve_api_keys()
    return keys[0] if keys else ""


def resolve_api_keys() -> list[str]:
    """Resolve the list of Gemini API keys.

    The ``gemini_api_key`` setting may hold a single key or a comma/newline
    separated list (multi-key pooling). Falls back to env/config if empty.
    """
    raw = _get_setting_value("gemini_api_key")
    if raw:
        keys = [k.strip() for k in raw.replace("\n", ",").split(",") if k.strip()]
        if keys:
            return keys
    env_key = settings.gemini_api_key or os.getenv("GEMINI_API_KEY", "")
    if env_key:
        return [k.strip() for k in env_key.replace("\n", ",").split(",") if k.strip()]
    return []


def normalize_model_name(name: str) -> str:
    """Strip a leading 'models/' prefix so values work with REST paths and LangChain."""
    name = (name or "").strip()
    if name.startswith("models/"):
        return name[len("models/"):]
    return name


def _ensure_models_prefix(name: str) -> str:
    """Ensure a model name carries the 'models/' prefix.

    The Gemini REST ``batchEmbedContents`` endpoint requires the fully-qualified
    'models/<name>' format.
    """
    name = (name or "").strip()
    if not name:
        return name
    if name.startswith("models/"):
        return name
    return f"models/{name}"


def resolve_chat_model() -> str:
    """Resolve the chat model: settings table -> config default (normalized)."""
    return normalize_model_name(_get_setting_value("gemini_chat_model") or settings.gemini_chat_model)


def resolve_rewrite_model() -> str:
    """Resolve the lightweight model used for query rewriting (settings table -> config default)."""
    return normalize_model_name(_get_setting_value("gemini_rewrite_model") or settings.gemini_rewrite_model)


def resolve_ocr_model() -> str:
    """Resolve the lightweight model used for image OCR (settings table -> config default)."""
    return normalize_model_name(_get_setting_value("gemini_ocr_model") or settings.gemini_ocr_model)


def resolve_embedding_model() -> str:
    """Resolve the embedding model: settings table -> config default (normalized)."""
    return normalize_model_name(_get_setting_value("gemini_embedding_model") or settings.gemini_embedding_model)


def get_embedding_function() -> Any:
    """Return a ChromaDB-compatible embedding function backed by the smart manager.

    ChromaDB calls ``__call__``/``embed_documents`` mainly at query time. All
    document ingestion is done manually via :func:`embed_batches_managed` with
    pre-computed embeddings, so ChromaDB never triggers API calls during upload.
    """
    keys = resolve_api_keys()
    key_manager.configure(keys)
    return GeminiChromaEmbeddingFunction(
        model=resolve_embedding_model(),
        api_keys=keys,
    )


class GeminiChromaEmbeddingFunction(EmbeddingFunction):
    """ChromaDB-native embedding function that delegates to the smart manager.

    Satisfies ChromaDB's protocol (``name()``, ``get_config()``,
    ``build_from_config()``) while routing every real embedding call through the
    decoupled :mod:`embedding_manager` — never a raw LangChain client.
    """

    def __init__(self, model: str, api_keys: list[str] | str):
        self._model = normalize_model_name(model)
        if isinstance(api_keys, str):
            api_keys = [k.strip() for k in api_keys.replace("\n", ",").split(",") if k.strip()]
        self._api_keys = list(api_keys)

    def __call__(self, input: list[str]) -> Embeddings:
        """ChromaDB calls the embedding function with a list of documents."""
        return embed_batch_managed(list(input), self._model)

    def name(self) -> str:
        """Stable name used by ChromaDB when persisting collection config."""
        return f"GeminiChromaEmbeddingFunction-{self._model}"

    def embed_documents(self, input: list[str]) -> list[list[float]]:
        return embed_batch_managed(list(input), self._model)

    def embed_query(self, input: str) -> Embeddings:
        if isinstance(input, str):
            return embed_batch_managed([input], self._model)
        return embed_batch_managed(list(input), self._model)

    def get_config(self) -> dict[str, Any]:
        """Return a serializable configuration so ChromaDB can rebuild this function."""
        return {"model": self._model, "api_keys": self._api_keys}

    @staticmethod
    def build_from_config(config: dict[str, Any]) -> "GeminiChromaEmbeddingFunction":
        """Rebuild the embedding function from a persisted config."""
        return GeminiChromaEmbeddingFunction(
            model=config.get("model", ""),
            api_keys=config.get("api_keys", []),
        )