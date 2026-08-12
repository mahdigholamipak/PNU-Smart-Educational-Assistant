from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Course
from app.schemas.course import CourseResponse

router = APIRouter(prefix="/courses", tags=["Courses"])


@router.get("", response_model=list[CourseResponse])
def list_active_courses(db: Session = Depends(get_db)):
    """List all active courses available for chat scoping."""
    return db.query(Course).filter(Course.is_active.is_(True)).order_by(Course.title).all()