"""Decoupled Smart Embedding Manager.

Completely decouples embedding generation from LangChain/ChromaDB's automatic
API call machinery. Drives the raw Gemini REST ``batchEmbedContents`` endpoint
directly with ``requests``, passing the API key as a URL query parameter on
every single request.

Why this is bulletproof for multi-key rate-limit resilience:

- There is no SDK client, no cached transport, no session to reuse — each HTTP
  call is a brand-new request bound to *exactly* the key in the URL.
- The :class:`SmartKeyManager` holds persistent per-key state (cooldown timers)
  and rotates keys proactively before every batch, so fresh keys are actually
  used instead of hammering an exhausted key.
- A 429 marks the offending key as "burned" for a cooldown window; the same
  batch is immediately retried with the next available key (never restarting
  the whole document).
"""

import threading
import time
from typing import Any

import requests

from app.config import settings
from app.database import SessionLocal
from app.models import ApiUsage


class RateLimitError(RuntimeError):
    """Raised when the Gemini embedding API returns HTTP 429."""


class SmartKeyManager:
    """Thread-safe singleton managing the state of all Gemini API keys.

    Tracks for each key whether it is available or cooling down after a 429.
    """

    def __init__(self):
        self._keys: list[str] = []
        self._index = 0
        self._cooldown_until: dict[str, float] = {}
        self._lock = threading.Lock()

    def configure(self, keys: list[str]) -> None:
        """(Re)configure the active key pool, preserving cooldowns for survivors."""
        with self._lock:
            self._keys = list(keys)
            self._cooldown_until = {
                k: v for k, v in self._cooldown_until.items() if k in self._keys
            }
            if self._index >= len(self._keys) and self._keys:
                self._index = self._index % len(self._keys)

    def acquire_key(self) -> str | None:
        """Return the next available (non-cooling) key, or None if all cooling.

        Proactively rotates the round-robin index on every call so batches are
        spread across all keys from the very beginning.
        """
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

    def report_429(self, key: str, cooldown: float | None = None) -> None:
        """Mark ``key`` as burned for ``cooldown`` seconds (default from config)."""
        if cooldown is None:
            cooldown = float(max(0, int(settings.embedding_key_cooldown)))
        with self._lock:
            self._cooldown_until[key] = time.monotonic() + cooldown

    def is_cooling(self, key: str) -> bool:
        """Return True if ``key`` is currently in cooldown."""
        now = time.monotonic()
        with self._lock:
            return self._cooldown_until.get(key, 0) > now

    def cooldown_remaining(self, key: str) -> float:
        """Return remaining cooldown seconds for ``key`` (0 if available)."""
        now = time.monotonic()
        with self._lock:
            return max(0.0, self._cooldown_until.get(key, 0) - now)

    @property
    def keys(self) -> list[str]:
        with self._lock:
            return list(self._keys)

    @staticmethod
    def _mask_key(api_key: str) -> str:
        """Return a masked version of the key for safe display/storage."""
        if len(api_key) <= 8:
            return "****"
        return f"{api_key[:4]}****{api_key[-4:]}"

    def record_usage(self, api_key: str, model: str, tokens: int) -> None:
        """Increment request/token counters for ``api_key`` in the DB.

        Uses its own DB session because the manager runs outside the request
        context. Failures here are swallowed so usage tracking never breaks the
        actual API call.
        """
        if not api_key:
            return
        masked = self._mask_key(api_key)
        tokens = max(0, int(tokens or 0))
        db = SessionLocal()
        try:
            row = db.query(ApiUsage).filter(ApiUsage.api_key_masked == masked).first()
            if row:
                row.total_requests += 1
                row.total_tokens_used += tokens
            else:
                row = ApiUsage(
                    api_key_masked=masked,
                    model=model or "unknown",
                    total_requests=1,
                    total_tokens_used=tokens,
                )
                db.add(row)
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()


# Module-level singleton so rotation state survives across all batches of a
# document and across successive uploads within the same process.
key_manager = SmartKeyManager()


def _embed_batch_raw(texts: list[str], model: str, api_key: str) -> list[list[float]]:
    """Embed one batch via the Gemini REST ``batchEmbedContents`` endpoint.

    The API key is sent as a URL query parameter on this single request — there
    is no cached client/session, so the key is guaranteed to be used.
    """
    from app.services.llm_service import _ensure_models_prefix, normalize_model_name

    # The URL path already contains a "models/" segment, so the model name must
    # be normalized (any leading "models/" stripped) to avoid a double prefix
    # such as ".../v1beta/models/models/gemini-embedding-2" -> 404.
    clean_model = normalize_model_name(model)  # e.g. "gemini-embedding-2"
    # The request body requires the fully-qualified "models/<name>" form.
    prefixed = _ensure_models_prefix(model)  # e.g. "models/gemini-embedding-2"
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/{clean_model}:"
        f"batchEmbedContents"
    )
    payload = {
        "requests": [
            {
                "model": prefixed,
                "content": {"parts": [{"text": text}]},
            }
            for text in texts
        ]
    }

    resp = requests.post(
        url,
        params={"key": api_key},
        json=payload,
        timeout=30,
    )

    if resp.status_code == 429:
        raise RateLimitError(f"429 rate limit exceeded for key: {resp.text[:500]}")
    if resp.status_code >= 400:
        raise RuntimeError(
            f"Gemini API returned HTTP {resp.status_code}: {resp.text[:1000]}"
        )

    data = resp.json()
    embeddings = []
    for item in data.get("embeddings", []):
        values = item.get("values") or []
        embeddings.append(values)
    if len(embeddings) != len(texts):
        raise RuntimeError(
            f"Embedding response count mismatch: got {len(embeddings)}, expected {len(texts)}"
        )

    # Record token usage for this key (best-effort; never breaks the call).
    usage = data.get("usageMetadata") or {}
    tokens = usage.get("totalTokenCount") or 0
    key_manager.record_usage(api_key, model, tokens)

    return embeddings


def embed_batch_managed(
    texts: list[str],
    model: str,
) -> list[list[float]]:
    """Embed one batch using the shared SmartKeyManager.

    Retries the *same* batch on 429 by marking the key as burned and rotating
    to the next available key (with exponential backoff when all keys cool).
    """
    if not key_manager.keys:
        raise RuntimeError("هیچ کلید API تنظیم نشده است. ابتدا کلید را در تنظیمات ذخیره کنید.")

    attempt = 0
    max_attempts = max(1, int(settings.embedding_max_retries))

    while attempt < max_attempts:
        api_key = key_manager.acquire_key()
        if api_key is None:
            delay = min(settings.embedding_backoff_base * (2 ** attempt), 60.0)
            time.sleep(delay)
            attempt += 1
            continue

        try:
            return _embed_batch_raw(texts, model, api_key)
        except RateLimitError:
            key_manager.report_429(api_key)
            attempt += 1
            continue

    raise RuntimeError(
        "محدودیت نرخ API (429) پس از چند بار تلاش برطرف نشد. "
        "لطفاً کلیدهای API بیشتری اضافه کنید یا بعداً دوباره تلاش کنید."
    )


def embed_batches_managed(
    chunks: list[str],
    model: str,
) -> list[list[float]]:
    """Embed all ``chunks`` in strict batches with proactive key rotation.

    Returns one embedding vector per chunk (aligned by index). A short
    inter-batch sleep prevents spiking the RPM budget.
    """
    batch_size = max(1, int(settings.embedding_batch_size))
    inter_batch_delay = max(0.0, float(settings.embedding_inter_batch_delay))

    all_embeddings: list[list[float]] = []

    for start in range(0, len(chunks), batch_size):
        batch = chunks[start:start + batch_size]
        batch_embeddings = embed_batch_managed(batch, model)
        all_embeddings.extend(batch_embeddings)

        if inter_batch_delay > 0 and start + batch_size < len(chunks):
            time.sleep(inter_batch_delay)

    if len(all_embeddings) != len(chunks):
        raise RuntimeError(
            f"Embedding count mismatch: got {len(all_embeddings)}, expected {len(chunks)}"
        )
    return all_embeddings