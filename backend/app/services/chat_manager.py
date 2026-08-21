"""Decoupled Smart Chat Generation Manager.

Applies the same resilient patterns as the embedding manager to the Gemini
chat/generation endpoint. Drives the raw REST ``generateContent`` endpoint
directly with ``requests``, passing the API key as a URL query parameter on
every request — no cached SDK client, no fragile wrapper.

Uses the shared :class:`SmartKeyManager` so chat generation benefits from
proactive key rotation, per-key cooldown on 429, and automatic retry of the
same prompt with the next available key.
"""

import base64
import re
import time
from typing import Any

import requests

from app.config import settings
from app.services.embedding_manager import RateLimitError, key_manager
from app.services.llm_service import resolve_api_keys, resolve_rewrite_model


def _extract_inline_data(image_data: str) -> tuple[str, str]:
    """Parse a Base64 data URL into ``(mime_type, base64_data)``.

    Accepts ``data:image/png;base64,iVBOR...`` style strings. The MIME type
    defaults to ``image/png`` if the prefix is malformed but a comma exists.
    Raises ``ValueError`` if the payload does not look like a data URL.
    """
    if not image_data or "," not in image_data:
        raise ValueError("image_data must be a Base64 data URL")

    header, _, b64 = image_data.partition(",")
    mime_type = ""
    if header.startswith("data:") and ";base64" in header:
        mime_type = header[len("data:"):].split(";", 1)[0]
    if not mime_type:
        mime_type = "image/png"

    # Validate it's actually base64 (strip whitespace/line breaks first).
    cleaned = re.sub(r"\s+", "", b64)
    if not cleaned:
        raise ValueError("image_data contains no base64 payload")
    try:
        base64.b64decode(cleaned, validate=True)
    except Exception as exc:
        raise ValueError(f"image_data is not valid base64: {exc}") from exc

    return mime_type, cleaned


def _generate_content_raw(
    messages: list[tuple[str, str]],
    model: str,
    api_key: str,
    system_prompt: str | None = None,
) -> str:
    """Generate a chat response via the Gemini REST ``generateContent`` endpoint.

    ``messages`` is a list of ``(role, content, image_data?)`` tuples where
    role is ``"system"`` or ``"human"`` and ``image_data`` is an optional
    Base64 data URL string (e.g. ``data:image/png;base64,...``). When an image
    is present it is embedded as a Gemini ``inline_data`` part alongside the
    text part, enabling multimodal analysis. The API key is sent as a URL query
    parameter on this single request — there is no cached client/session.

    ``system_prompt``, when provided, is sent in Gemini's dedicated
    ``systemInstruction`` field so the model's instructions are cleanly
    separated from the conversational ``contents`` turns. This lets the
    model's native attention mechanism weight the real dialogue (alternating
    user/model) instead of a giant instruction blob merged into a user turn.
    """
    from app.services.llm_service import _ensure_models_prefix, normalize_model_name

    clean_model = normalize_model_name(model)  # e.g. "gemini-2.5-flash"
    prefixed = _ensure_models_prefix(model)  # e.g. "models/gemini-2.5-flash"

    # Build the Gemini contents array from (role, content[, image_data]) tuples.
    contents = []
    for item in messages:
        role = item[0]
        content = item[1] if len(item) > 1 else ""
        image_data = item[2] if len(item) > 2 else None
        parts: list[dict[str, Any]] = []

        if image_data:
            mime_type, b64 = _extract_inline_data(image_data)
            parts.append({"inline_data": {"mime_type": mime_type, "data": b64}})
            if content:
                parts.append({"text": content})
        elif content:
            parts.append({"text": content})

        if role in ("system", "human", "user"):
            # Gemini has no system role; prepend as a user instruction.
            contents.append({"role": "user", "parts": parts})
        elif role in ("assistant", "ai", "model"):
            # Gemini's model role represents the assistant's prior responses.
            # Inline images are NOT allowed in model turns — refuse to build
            # an invalid payload so this can never silently corrupt the request.
            if image_data:
                raise ValueError(
                    "image_data cannot be attached to a model (assistant) turn. "
                    "Attach images only to the current user turn."
                )
            contents.append({"role": "model", "parts": parts})
        else:
            # Unknown role — safest to treat as user.
            contents.append({"role": "user", "parts": parts})

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/{clean_model}:"
        f"generateContent"
    )
    payload: dict[str, Any] = {
        "contents": contents,
        "generationConfig": {"temperature": 0.2},
    }
    if system_prompt:
        payload["systemInstruction"] = {"parts": [{"text": system_prompt}]}

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
    system_prompt: str | None = None,
) -> str:
    """Generate a chat response using the shared SmartKeyManager.

    Retries the *same* prompt on 429 by marking the key as burned and rotating
    to the next available key (with exponential backoff when all keys cool).

    ``system_prompt`` is forwarded to Gemini's ``systemInstruction`` field
    (optional; used by the RAG answer generator for its system rules).
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
            return _generate_content_raw(messages, model, api_key, system_prompt)
        except RateLimitError:
            key_manager.report_429(api_key)
            attempt += 1
            continue

    raise RuntimeError(
        "محدودیت نرخ API (429) پس از چند بار تلاش برطرف نشد. "
        "لطفاً کلیدهای API بیشتری اضافه کنید یا بعداً دوباره تلاش کنید."
    )


# System prompt for generating a short, meaningful chat title from the first
# user message (or OCR-extracted image text). Kept lightweight so the title
# is concise and never leaks internal instructions.
TITLE_SYSTEM_PROMPT = """You are a helpful assistant that names chat conversations.
Given the user's first message (which may be OCR text extracted from an image),
produce a SHORT, meaningful Persian title (max 30 characters) that summarizes
the topic. Output ONLY the title — no quotes, prefixes, or explanations.
If the input is empty or unreadable, output "گفتگو".
"""


def generate_chat_title(text: str) -> str:
    """Generate a short, meaningful chat title from the first user message.

    Uses a lightweight Gemini model via the shared SmartKeyManager. Any failure
    (no keys, rate limit, network) falls back to a truncated version of the
    input text so chat creation NEVER breaks.
    """
    text = (text or "").strip()
    if not text:
        return "گفتگو"

    # CRITICAL: ensure the smart key pool is configured before the LLM call.
    key_manager.configure(resolve_api_keys())

    try:
        messages = [("user", f"{TITLE_SYSTEM_PROMPT}\n\nمتن کاربر:\n{text}")]
        title = generate_chat_response(messages, resolve_rewrite_model())
        title = title.strip().strip('"').strip("«»").strip()
        if title and len(title) <= 60:
            return title
    except Exception:
        # Any failure → fall through to the deterministic fallback.
        pass

    # Deterministic fallback: truncate the input to a reasonable title length.
    return text[:30]
