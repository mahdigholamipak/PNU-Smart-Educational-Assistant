from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database import get_db
from app.models import CourseRequest, User
from app.schemas.request import CourseRequestCreate, CourseRequestResponse

router = APIRouter(prefix="/requests", tags=["Course Requests"])


@router.post("", response_model=CourseRequestResponse, status_code=status.HTTP_201_CREATED)
def create_course_request(
    payload: CourseRequestCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Submit a request for a new course to be added."""
    request = CourseRequest(
        user_id=current_user.id,
        course_name=payload.course_name,
        course_code=payload.course_code,
        description=payload.description,
    )
    db.add(request)
    db.commit()
    db.refresh(request)
    return request


@router.get("/me", response_model=list[CourseRequestResponse])
def list_my_requests(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List the current user's course requests."""
    return (
        db.query(CourseRequest)
        .filter(CourseRequest.user_id == current_user.id)
        .order_by(CourseRequest.created_at.desc())
        .all()
    )