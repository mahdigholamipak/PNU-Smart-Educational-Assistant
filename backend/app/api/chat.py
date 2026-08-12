import json

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
from app.services.rag_service import generate_rag_answer

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
    """Create a new chat session scoped to a course."""
    course = db.query(Course).filter(Course.id == payload.course_id, Course.is_active.is_(True)).first()
    if not course:
        raise HTTPException(status_code=404, detail="درس مورد نظر یافت نشد")

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
        .order_by(ChatSession.created_at.desc())
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
        messages=messages,
    )


@router.post("/sessions/{session_id}/messages")
def send_message(
    session_id: int,
    payload: SendMessageRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Send a user message and receive a RAG-based assistant answer."""
    session = _get_owned_session(session_id, current_user.id, db)

    # Persist the user message
    user_message = ChatMessage(session_id=session.id, role="user", content=payload.content)
    db.add(user_message)
    db.commit()

    # Generate RAG answer scoped to the session's course
    answer, sources = generate_rag_answer(
        question=payload.content,
        course_id=session.course_id,
        db=db,
    )

    assistant_message = ChatMessage(
        session_id=session.id,
        role="assistant",
        content=answer,
        sources_json=json.dumps(sources, ensure_ascii=False) if sources else None,
    )
    db.add(assistant_message)
    db.commit()
    db.refresh(assistant_message)

    return {
        "id": assistant_message.id,
        "role": assistant_message.role,
        "content": assistant_message.content,
        "sources": sources,
        "created_at": assistant_message.created_at,
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