"""Decoupled Smart Chat Generation Manager.

Applies the same resilient patterns as the embedding manager to the Gemini
chat/generation endpoint. Drives the raw REST ``generateContent`` endpoint
directly with ``requests``, passing the API key as a URL query parameter on
every request — no cached SDK client, no fragile wrapper.

Uses the shared :class:`SmartKeyManager` so chat generation benefits from
proactive key rotation, per-key cooldown on 429, and automatic retry of the
same prompt with the next available key.
"""

import time
from typing import Any

import requests

from app.config import settings
from app.services.embedding_manager import RateLimitError, key_manager


def _generate_content_raw(
    messages: list[tuple[str, str]],
    model: str,
    api_key: str,
) -> str:
    """Generate a chat response via the Gemini REST ``generateContent`` endpoint.

    ``messages`` is a list of ``(role, content)`` tuples where role is
    ``"system"`` or ``"human"``. The API key is sent as a URL query parameter
    on this single request — there is no cached client/session.
    """
    from app.services.llm_service import _ensure_models_prefix, normalize_model_name

    clean_model = normalize_model_name(model)  # e.g. "gemini-2.5-flash"
    prefixed = _ensure_models_prefix(model)  # e.g. "models/gemini-2.5-flash"

    # Build the Gemini contents array from (role, content) tuples.
    contents = []
    for role, content in messages:
        if role == "system":
            # Gemini has no system role; prepend as a user instruction.
            contents.append({"role": "user", "parts": [{"text": content}]})
        else:
            contents.append({"role": "user", "parts": [{"text": content}]})

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/{clean_model}:"
        f"generateContent"
    )
    payload = {
        "contents": contents,
        "generationConfig": {"temperature": 0.2},
    }

    resp = requests.post(
        url,
        params={"key": api_key},
        json=payload,
        timeout=60,
    )

    if resp.status_code == 429:
        raise RateLimitError("429 rate limit exceeded for chat generation")
    resp.raise_for_status()

    data = resp.json()
    candidates = data.get("candidates") or []
    if not candidates:
        raise RuntimeError("Gemini returned no candidates")
    parts = (candidates[0].get("content") or {}).get("parts") or []
    if not parts:
        raise RuntimeError("Gemini returned empty content")

    # Record token usage for this key (best-effort; never breaks the call).
    usage = data.get("usageMetadata") or {}
    tokens = usage.get("totalTokenCount") or 0
    key_manager.record_usage(api_key, model, tokens)

    return parts[0].get("text", "")


def generate_chat_response(
    messages: list[tuple[str, str]],
    model: str,
) -> str:
    """Generate a chat response using the shared SmartKeyManager.

    Retries the *same* prompt on 429 by marking the key as burned and rotating
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
            return _generate_content_raw(messages, model, api_key)
        except RateLimitError:
            key_manager.report_429(api_key)
            attempt += 1
            continue

    raise RuntimeError(
        "محدودیت نرخ API (429) پس از چند بار تلاش برطرف نشد. "
        "لطفاً کلیدهای API بیشتری اضافه کنید یا بعداً دوباره تلاش کنید."
    )