import os
import threading
import time
from typing import Any

from chromadb.api.types import EmbeddingFunction, Embeddings
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_google_genai._common import GoogleGenerativeAIError

from app.config import settings
from app.database import SessionLocal
from app.models import Setting


def _get_setting_value(key: str) -> str:
    """Read a setting value from the admin-managed settings table."""
    db = SessionLocal()
    try:
        setting = db.query(Setting).filter(Setting.key == key).first()
        return setting.value if setting and setting.value else ""
    finally:
        db.close()


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

    LangChain's GoogleGenerativeAIEmbeddings uses the batchEmbedContents API,
    which requires the fully-qualified 'models/<name>' format. The REST
    generateContent/embedContent endpoints tolerate both, but batch doesn't.
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


def resolve_embedding_model() -> str:
    """Resolve the embedding model: settings table -> config default (normalized)."""
    return normalize_model_name(_get_setting_value("gemini_embedding_model") or settings.gemini_embedding_model)


def _is_rate_limit_error(exc: Exception) -> bool:
    """Return True if the exception indicates a 429 / quota / rate-limit error."""
    msg = str(exc).lower()
    return "429" in msg or "quota" in msg or "rate limit" in msg or "resource exhausted" in msg


class _KeyPool:
    """Thread-safe round-robin pool of Gemini API keys with per-key cooldown.

    When a key hits a 429, it is marked as "cooling down" for a backoff window
    and the pool rotates to the next key. This lets a large PDF continue
    embedding across multiple keys instead of failing the whole upload.
    """

    def __init__(self, keys: list[str]):
        self._keys = list(keys)
        self._index = 0
        self._cooldown_until: dict[str, float] = {}
        self._lock = threading.Lock()

    def next_key(self) -> str | None:
        """Return the next available (non-cooling) key, or None if all cooling."""
        if not self._keys:
            return None
        now = time.monotonic()
        with self._lock:
            for _ in range(len(self._keys)):
                key = self._keys[self._index % len(self._keys)]
                self._index += 1
                if self._cooldown_until.get(key, 0) <= now:
                    return key
        return None

    def mark_rate_limited(self, key: str, cooldown: float) -> None:
        """Put a key into cooldown for ``cooldown`` seconds after a 429."""
        with self._lock:
            self._cooldown_until[key] = time.monotonic() + cooldown

    def reset(self) -> None:
        """Clear all cooldowns (e.g. after a successful call)."""
        with self._lock:
            self._cooldown_until.clear()


def _embed_batch_with_retry(
    texts: list[str],
    model: str,
    keys: list[str],
) -> list[list[float]]:
    """Embed a batch of texts with multi-key failover + exponential backoff.

    Strategy:
      1. Round-robin across the key pool.
      2. On 429, mark the key as cooling down and try the next key.
      3. If all keys are cooling, sleep with exponential backoff and retry.
      4. Non-429 errors are raised immediately (they won't be fixed by retry).
    """
    if not keys:
        raise RuntimeError("هیچ کلید API تنظیم نشده است. ابتدا کلید را در تنظیمات ذخیره کنید.")

    pool = _KeyPool(keys)
    prefixed_model = _ensure_models_prefix(model)
    attempt = 0
    max_attempts = settings.embedding_max_retries

    while attempt < max_attempts:
        key = pool.next_key()
        if key is None:
            # All keys cooling down -> exponential backoff
            delay = min(settings.embedding_backoff_base * (2 ** attempt), 60.0)
            time.sleep(delay)
            attempt += 1
            continue

        embeddings = GoogleGenerativeAIEmbeddings(
            model=prefixed_model,
            google_api_key=key,
        )
        try:
            result = embeddings.embed_documents(list(texts))
            pool.reset()
            return result
        except GoogleGenerativeAIError as exc:
            if _is_rate_limit_error(exc):
                pool.mark_rate_limited(key, settings.embedding_backoff_base * (2 ** attempt))
                attempt += 1
                continue
            raise
        except Exception:
            # Non-rate-limit errors: don't burn the key, just re-raise.
            raise

    raise RuntimeError(
        "محدودیت نرخ API (429) پس از چند بار تلاش برطرف نشد. "
        "لطفاً کلیدهای API بیشتری اضافه کنید یا بعداً دوباره تلاش کنید."
    )


class GeminiChromaEmbeddingFunction(EmbeddingFunction):
    """ChromaDB-native embedding function backed by GoogleGenerativeAIEmbeddings.

    ChromaDB expects an embedding function exposing ``__call__(input)``, ``name()``,
    ``build_from_config()`` and ``get_config()``. LangChain embeddings only expose
    ``embed_documents``/``embed_query``, which causes the
    ``AttributeError: 'GoogleGenerativeAIEmbeddings' object has no attribute 'name'`` crash
    when a raw LangChain object is passed to a native ChromaDB client method.

    This class subclasses ``chromadb.api.types.EmbeddingFunction`` so ChromaDB can
    serialize/restore the embedding configuration across client restarts without errors.
    It also supports multiple API keys with round-robin failover + backoff.
    """

    def __init__(self, model: str, api_keys: list[str] | str):
        self._model = normalize_model_name(model)
        if isinstance(api_keys, str):
            api_keys = [k.strip() for k in api_keys.replace("\n", ",").split(",") if k.strip()]
        self._api_keys = list(api_keys)
        self._pool = _KeyPool(self._api_keys)

    def __call__(self, input: list[str]) -> Embeddings:
        """ChromaDB calls the embedding function with a list of documents."""
        return _embed_batch_with_retry(list(input), self._model, self._api_keys)

    def name(self) -> str:
        """Stable name used by ChromaDB when persisting collection config."""
        return f"GeminiChromaEmbeddingFunction-{self._model}"

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return _embed_batch_with_retry(list(texts), self._model, self._api_keys)

    def embed_query(self, text: str) -> list[float]:
        return _embed_batch_with_retry([text], self._model, self._api_keys)[0]

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


def get_embedding_function() -> Any:
    """Return the ChromaDB-compatible Gemini embedding function (multi-key aware)."""
    return GeminiChromaEmbeddingFunction(
        model=resolve_embedding_model(),
        api_keys=resolve_api_keys(),
    )


def get_chat_model():
    """Return the Gemini chat model for RAG answer generation."""
    return ChatGoogleGenerativeAI(
        model=resolve_chat_model(),
        google_api_key=resolve_api_key(),
        temperature=0.2,
    )