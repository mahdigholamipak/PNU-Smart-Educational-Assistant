import json
import traceback
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database import get_db
from app.models import ChatMessage, ChatSession, Course, User
from app.schemas.chat import (
    ChatSessionCreate,
    ChatSessionDetailResponse,
    ChatSessionResponse,
    SendMessageRequest,
)
from app.services.chat_manager import generate_chat_title
from app.services.conversation_memory import get_recent_messages
from app.services.log_service import log_event
from app.services.rag_service import (
    KIND_AI_CONNECTION,
    extract_image_text,
    generate_rag_answer,
)

router = APIRouter(prefix="/chat", tags=["Chat"])


def _get_owned_session(session_id: int, user_id: int, db: Session) -> ChatSession:
    session = db.query(ChatSession).filter(ChatSession.id == session_id, ChatSession.user_id == user_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="گفتگو یافت نشد")
    return session


@router.post("/sessions", response_model=ChatSessionResponse, status_code=201)
def create_session(
    payload: ChatSessionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new chat session scoped to a course.

    Reuses an existing EMPTY session for this user+course if one exists, so we
    don't pile up duplicate empty sessions in the history list.
    """
    course = db.query(Course).filter(Course.id == payload.course_id, Course.is_active.is_(True)).first()
    if not course:
        raise HTTPException(status_code=404, detail="درس مورد نظر یافت نشد")

    existing = (
        db.query(ChatSession)
        .filter(
            ChatSession.user_id == current_user.id,
            ChatSession.course_id == course.id,
        )
        .order_by(ChatSession.updated_at.desc())
        .first()
    )
    if existing is not None and not existing.messages:
        # Reuse the empty session: bump its timestamp so it floats to the top.
        existing.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(existing)
        return ChatSessionResponse(
            id=existing.id,
            course_id=existing.course_id,
            course_title=course.title,
            title=existing.title,
            created_at=existing.created_at,
            updated_at=existing.updated_at,
        )

    session = ChatSession(user_id=current_user.id, course_id=course.id, title=course.title)
    db.add(session)
    db.commit()
    db.refresh(session)
    return ChatSessionResponse(
        id=session.id,
        course_id=session.course_id,
        course_title=course.title,
        title=session.title,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


@router.get("/sessions", response_model=list[ChatSessionResponse])
def list_sessions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List the current user's chat sessions (newest first)."""
    sessions = (
        db.query(ChatSession)
        .filter(ChatSession.user_id == current_user.id)
        .order_by(ChatSession.updated_at.desc())
        .all()
    )
    result = []
    for session in sessions:
        result.append(
            ChatSessionResponse(
                id=session.id,
                course_id=session.course_id,
                course_title=session.course.title if session.course else None,
                title=session.title,
                created_at=session.created_at,
                updated_at=session.updated_at,
            )
        )
    return result


@router.get("/sessions/{session_id}", response_model=ChatSessionDetailResponse)
def get_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a chat session with its full message history."""
    session = _get_owned_session(session_id, current_user.id, db)
    messages = []
    for msg in session.messages:
        sources = None
        if msg.sources_json:
            try:
                sources = json.loads(msg.sources_json)
            except json.JSONDecodeError:
                sources = None
        messages.append(
            {
                "id": msg.id,
                "role": msg.role,
                "content": msg.content,
                "image": msg.image_data,
                "sources": sources,
                "created_at": msg.created_at,
            }
        )
    return ChatSessionDetailResponse(
        id=session.id,
        course_id=session.course_id,
        course_title=session.course.title if session.course else None,
        title=session.title,
        created_at=session.created_at,
        updated_at=session.updated_at,
        messages=messages,
    )


@router.post("/sessions/{session_id}/messages")
def send_message(
    session_id: int,
    payload: SendMessageRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Send a user message and receive a RAG-based assistant answer.

    If ``payload.session_id`` is provided it takes precedence over the path
    parameter. A provided session_id NEVER creates a new session — it only
    appends the message to the existing (owned) session and bumps its
    ``updated_at`` timestamp.
    """
    # Strictly enforce: if a session_id is supplied in the payload, use it and
    # never create a new session. Fall back to the path parameter otherwise.
    target_id = payload.session_id if payload.session_id is not None else session_id
    session = _get_owned_session(target_id, current_user.id, db)

    # Fetch recent conversation history BEFORE persisting the current message,
    # so the memory window excludes the new turn itself.
    history = get_recent_messages(db, session.id, max_turns=6)

    # Persist the user message. For image-only messages (no text), store a
    # friendly placeholder so the bubble and history aren't blank. The raw
    # image (Base64 data URL) is persisted too so the chat/history UI can
    # re-render the actual screenshot thumbnail on reload.
    display_content = payload.content.strip() or "📷 تصویر"
    user_message = ChatMessage(
        session_id=session.id,
        role="user",
        content=display_content,
        image_data=payload.image_data or None,
    )
    db.add(user_message)

    # Pre-computed OCR text for image-only prompts. Initialized empty; set only
    # when we actually extract the image's text (used for both the title and
    # the RAG pipeline to avoid a duplicate OCR call).
    ocr_text = ""

    # Dynamic session naming: use the first prompt as the title if the session
    # still carries the default course title (i.e., no custom title yet).
    # For image-only prompts (no text), WAIT for OCR to complete and pass the
    # extracted text to the LLM title generator so the chat gets a meaningful
    # title based on the image's actual content instead of a generic string.
    if session.title == (session.course.title if session.course else None):
        if payload.content.strip():
            session.title = display_content[:30]
        elif payload.image_data:
            # Extract the image's text ONCE — reused for both the title and the
            # RAG pipeline (avoids a duplicate OCR call).
            ocr_text = extract_image_text(payload.image_data)
            session.title = generate_chat_title(ocr_text)
        else:
            session.title = display_content[:30]

    # Bump "last edited" timestamp so the session rises to the top of history.
    session.updated_at = datetime.utcnow()
    db.commit()

    # Generate RAG answer scoped to the session's course.
    # The optional image (Base64 data URL) is passed ONLY to the LLM for
    # multimodal analysis — the ChromaDB vector search stays text-only.
    # For image-only prompts, the OCR text extracted above is passed along so
    # the pipeline skips its internal (duplicate) OCR call.
    # Wrap the entire generation block so ANY exception is logged with a full
    # stack trace and surfaced to the user — never swallowed silently.
    try:
        answer, sources, error_kind, error_detail = generate_rag_answer(
            question=payload.content,
            course_id=session.course_id,
            db=db,
            history=history,
            image_data=payload.image_data,
            image_text=ocr_text if payload.image_data and not payload.content.strip() else "",
        )
    except Exception:
        log_event(
            db,
            level="error",
            source="chat",
            message="خطای غیرمنتظره در تولید پاسخ",
            details=f"{traceback.format_exc()}\ncourse_id={session.course_id} — question='{payload.content[:200]}'",
            commit=True,
        )
        raise HTTPException(
            status_code=502,
            detail="خطا در دریافت پاسخ. جزئیات کامل در لاگ سیستم ثبت شد.",
        )

    # If AI connection failed, log the REAL error and surface a transparent error
    if error_kind == KIND_AI_CONNECTION:
        log_event(
            db,
            level="error",
            source="chat",
            message="ارتباط با مدل هوش مصنوعی شکست خورد",
            details=(
                f"course_id={session.course_id} — question='{payload.content[:200]}'\n"
                f"error_detail={error_detail or 'unknown'}"
            ),
        )
        raise HTTPException(
            status_code=502,
            detail=(
                "ارتباط با مدل هوش مصنوعی برقرار نشد "
                "(محدودیت API یا خطای شبکه). لطفاً بعداً دوباره تلاش کنید."
            ),
        )

    assistant_message = ChatMessage(
        session_id=session.id,
        role="assistant",
        content=answer,
        sources_json=json.dumps(sources, ensure_ascii=False) if sources else None,
    )
    db.add(assistant_message)
    # Bump "last edited" timestamp again after the AI reply is persisted.
    session.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(assistant_message)

    return {
        "id": assistant_message.id,
        "role": assistant_message.role,
        "content": assistant_message.content,
        "sources": sources,
        "created_at": assistant_message.created_at,
        # Include the persisted user message's image so the frontend can
        # reconcile its temp message with the DB-backed one on reload.
        "user_message": {
            "id": user_message.id,
            "role": user_message.role,
            "content": user_message.content,
            "image": user_message.image_data,
            "created_at": user_message.created_at,
        },
    }


@router.delete("/sessions/{session_id}", status_code=204)
def delete_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a chat session and its messages."""
    session = _get_owned_session(session_id, current_user.id, db)
    db.delete(session)
    db.commit()