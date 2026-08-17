"""Conversation memory helpers for the RAG pipeline.

Responsible for:
- Fetching recent conversation history for a session (used both for the
  Gemini generation window and to detect when a follow-up needs rewriting).
- Rewriting a user's (possibly ambiguous) follow-up question into a
  standalone vector-search query via a lightweight Gemini-Flash LLM call,
  with a deterministic concatenation fallback for ANY AI failure.
"""

import re

from sqlalchemy.orm import Session

from app.models import ChatMessage
from app.services.chat_manager import generate_chat_response
from app.services.llm_service import resolve_rewrite_model

# Number of recent messages (turns) to feed into generation + rewriting.
HISTORY_MAX_TURNS = 6
# Hard cap on how much of a single history message we send (token savings).
_MAX_TURN_CHARS = 400

REWRITE_SYSTEM_PROMPT = """تو یک دستیار بازنویسی پرس‌وجو هستی. وظیفه تو این است که پرس‌وجوی فعلی کاربر را
با توجه به گفتگوی قبلی، به یک پرس‌وجوی مستقل و کامل برای جستجو در فهرست اسناد درسی تبدیل کنی.

قوانین:
1. فقط متن پرس‌وجوی بازنویسی‌شده را خروجی بده — هیچ توضیح، پیشوند، نقل‌قول یا نشانه‌گذاری اضافه نکن.
2. زبان متن را حفظ کن (فارسی/انگلیسی).
3. اگر پرس‌وجوی فعلی از قبل مستقل و کامل است، آن را عیناً تکرار کن.
4. اگر پرس‌وجوی فعلی کوتاه یا مبهم است (مثلاً «بیشتر توضیح بده»، «منظورت چیست؟»، «چرا؟»)،
   موضوع اصلی گفتگو را از پیام‌های قبلی استخراج کن و آن را در پرس‌وجو بگنجان.
   مثال: گفتگو درباره «ماشین تورینگ» -> ورودی «بیشتر توضیح بده» -> «بیشتر توضیح بده درباره ماشین تورینگ»
5. هرگز به «سیستم» یا «فهرست اسناد» اشاره نکن — فقط متن پرس‌وجو را خروج بده.
"""


def _trim_turn(content: str, max_chars: int = _MAX_TURN_CHARS) -> str:
    """Trim a message turn to avoid blowing the prompt budget."""
    content = " ".join(content.split())
    if len(content) <= max_chars:
        return content
    return content[:max_chars].rstrip() + "…"


def get_recent_messages(
    db: Session,
    session_id: int,
    max_turns: int = HISTORY_MAX_TURNS,
) -> list[dict]:
    """Fetch the last ``max_turns`` messages for a session, oldest-first.

    Returns a list of ``{"role": "user"|"assistant", "content": str}`` dicts
    ordered chronologically (oldest first). Used both for the Gemini
    generation window and for query rewriting.
    """
    messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.id.desc())
        .limit(max_turns)
        .all()
    )
    # Reverse to chronological order (oldest first).
    messages.reverse()
    return [
        {"role": msg.role, "content": _trim_turn(msg.content)}
        for msg in messages
    ]


def build_gemini_history(
    history: list[dict],
    current_user_message: str,
) -> list[tuple[str, str]]:
    """Build a compact alternating user/model chat history for Gemini.

    Takes the persisted ``history`` (list of role/content dicts) and appends
    the current user message. Returns a list of ``(role, content)`` tuples
    where the assistant's role is ``"assistant"`` so ``chat_manager`` can map
    it to Gemini's ``model`` role.

    Consecutive same-role messages are merged to satisfy Gemini's
    alternating-roles requirement.
    """
    turns: list[tuple[str, str]] = []
    for msg in history:
        role = "assistant" if msg["role"] == "assistant" else "user"
        content = msg["content"]
        if turns and turns[-1][0] == role:
            # Merge consecutive same-role messages.
            prev_role, prev_content = turns[-1]
            turns[-1] = (prev_role, f"{prev_content}\n\n{content}")
        else:
            turns.append((role, content))

    # Append the current user message (always ensures we end on a user turn).
    if turns and turns[-1][0] == "user":
        turns[-1] = ("user", f"{turns[-1][1]}\n\n{current_user_message}")
    else:
        turns.append(("user", current_user_message))

    return turns


def _needs_rewriting(question: str, history: list[dict]) -> bool:
    """Heuristically detect whether the current question is a short follow-up."""
    if len(history) < 2:  # Need at least one prior exchange.
        return False

    question = question.strip()
    if not question:
        return False

    # A question is probably self-contained if it's reasonably long (>3 words)
    # or contains Persian question words / grammatical completeness.
    words = question.split()
    if len(words) >= 4:
        return False

    # Short phrases like "بیشتر توضیح بده", "چرا؟", "منظورت چیست", "توضیح بده",
    # "explain more", "more please", etc. signal a follow-up.
    short_indicators = [
        "توضیح", "بیشتر", "چرا", "یعنی", "منظورت", "بقیه", "ادامه",
        "مثال بزن", "مثال", "شرح", "توضیح بده", "مثل چه", "مثلا",
        "explain", "more", "why", "what do you mean", "continue", "detail",
        "میشه بیشتر", "لطفا بیشتر", "لطفاً بیشتر",
    ]
    q_lower = question.lower()
    if any(ind in q_lower for ind in short_indicators):
        return True

    # Very short questions (e.g. ",", within the allowed 8000-char limit but
    # practically 1-3 words) are treated as follow-ups.
    return len(question) <= 20


def _fallback_rewrite(question: str, history: list[dict]) -> str:
    """Heuristic fallback when the LLM rewrite fails: concatenate the last
    user topic with the current short input."""
    # Find the last user question from history (oldest → newest).
    last_user_text = ""
    for msg in reversed(history):
        if msg["role"] == "user":
            last_user_text = msg["content"]
            break

    if not last_user_text:
        return question

    q = question.strip().rstrip("؟?")
    last_s = last_user_text.strip()

    # Simple heuristic: strip trailing punctuation and append the topic.
    # e.g. last: "ماشین تورینگ چیست؟"  current: "بیشتر توضیح بده"
    # → "ماشین تورینگ چیست؟ بیشتر توضیح بده"
    core_topic = re.sub(r"[؟?]+$", "", last_s)
    return f"{core_topic}؟ {q}".strip()


def rewrite_search_query(
    question: str,
    history: list[dict],
) -> str:
    """Rewrite the user's ambiguous follow-up into a standalone vector query.

    Strategy:
    1. If there is no history or the question is already self-contained,
       return it unchanged.
    2. Otherwise, call a lightweight Gemini model (Gemini-Flash) with the
       compact conversation transcript + system prompt to produce a
       standalone query.
    3. If the LLM call fails OR returns an unusable answer, fall back to a
       deterministic concatenation of the last user question + current input.
    """
    if not _needs_rewriting(question, history):
        return question

    # Build a compact transcript for the rewrite prompt.
    transcript_lines = []
    for msg in history[-HISTORY_MAX_TURNS:]:
        role_label = "دانشجو" if msg["role"] == "user" else "دستیار"
        transcript_lines.append(f"{role_label}: {msg['content']}")
    transcript = "\n".join(transcript_lines)

    prompt = (
        f"گفتگوی اخیر:\n{transcript}\n\n"
        f"پرس‌وجوی فعلی کاربر:\n{question}\n\n"
        "لطفاً فقط پرس‌وجوی مستقل و کامل را خروج بده (بدون هیچ توضیح اضافه)."
    )

    try:
        # Merge the system instruction and user prompt into a SINGLE user turn
        # (Gemini has no "system" role; both become "user" at the wire level,
        # so two consecutive user turns must be avoided).
        rewrite_messages = [("user", f"{REWRITE_SYSTEM_PROMPT}\n\n{prompt}")]
        rewritten = generate_chat_response(rewrite_messages, resolve_rewrite_model())
        rewritten = rewritten.strip().strip('"').strip("«»").strip()
        if rewritten and len(rewritten) <= 500:
            return rewritten
    except Exception:
        # Any failure → fall through to the deterministic fallback.
        pass

    return _fallback_rewrite(question, history)


def has_history(history: list[dict]) -> bool:
    """Return True if the given history contains at least one message."""
    return bool(history)
