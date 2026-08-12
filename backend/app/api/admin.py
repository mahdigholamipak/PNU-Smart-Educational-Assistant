import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.config import settings
from app.core.deps import require_admin
from app.database import get_db
from app.models import Course, CourseRequest, Resource, Setting, User
from app.schemas.course import CourseCreateRequest, CourseResponse, CourseUpdateRequest
from app.schemas.request import CourseRequestAdminUpdate, CourseRequestResponse
from app.schemas.resource import ResourceResponse, SettingResponse, SettingUpdateRequest
from app.schemas.user import PublicUserResponse
from app.services.document_service import process_pdf
from app.services.vector_store import add_document_chunks, delete_course_collection, delete_resource_chunks

router = APIRouter(prefix="/admin", tags=["Admin"], dependencies=[Depends(require_admin)])


def _serialize_resource(resource: Resource, course_title: str | None = None) -> ResourceResponse:
    return ResourceResponse(
        id=resource.id,
        course_id=resource.course_id,
        course_title=course_title or (resource.course.title if resource.course else None),
        filename=resource.filename,
        status=resource.status,
        chunk_count=resource.chunk_count,
        uploaded_at=resource.uploaded_at,
    )


# ---------- User Management ----------


@router.get("/users", response_model=list[PublicUserResponse])
def list_users(db: Session = Depends(get_db)):
    """List all registered users."""
    return db.query(User).order_by(User.created_at.desc()).all()


@router.patch("/users/{user_id}", response_model=PublicUserResponse)
def update_user(
    user_id: int,
    is_active: bool | None = None,
    role: str | None = None,
    db: Session = Depends(get_db),
):
    """Activate/deactivate a user or change their role."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="کاربر یافت نشد")

    if is_active is not None:
        user.is_active = is_active
    if role is not None:
        if role not in ("student", "admin"):
            raise HTTPException(status_code=400, detail="نقش نامعتبر است")
        user.role = role

    db.commit()
    db.refresh(user)
    return user


# ---------- Resource Management ----------


@router.get("/resources", response_model=list[ResourceResponse])
def list_resources(db: Session = Depends(get_db)):
    """List all uploaded resources."""
    resources = db.query(Resource).order_by(Resource.uploaded_at.desc()).all()
    return [_serialize_resource(r) for r in resources]


@router.post("/resources/upload", response_model=ResourceResponse, status_code=status.HTTP_201_CREATED)
async def upload_resource(
    course_id: int = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Upload a PDF, parse it, and embed its chunks into ChromaDB."""
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="درس مورد نظر یافت نشد")

    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="فقط فایل‌های PDF پشتیبانی می‌شوند")

    # Save file
    course_dir = settings.upload_path / str(course_id)
    course_dir.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid.uuid4().hex}_{file.filename}"
    stored_path = course_dir / stored_name
    stored_path.write_bytes(await file.read())

    resource = Resource(
        course_id=course_id,
        filename=file.filename,
        stored_path=str(stored_path),
        status="processing",
    )
    db.add(resource)
    db.commit()
    db.refresh(resource)

    # Process: extract text -> chunk -> embed
    try:
        chunks = process_pdf(stored_path)
        if not chunks:
            resource.status = "failed"
            db.commit()
            db.refresh(resource)
            return _serialize_resource(resource, course.title)

        chunk_count = add_document_chunks(
            course_id=course_id,
            resource_id=resource.id,
            filename=resource.filename,
            chunks=chunks,
        )
        resource.status = "ready"
        resource.chunk_count = chunk_count
        db.commit()
        db.refresh(resource)
    except Exception:
        resource.status = "failed"
        db.commit()
        db.refresh(resource)

    return _serialize_resource(resource, course.title)


@router.delete("/resources/{resource_id}", status_code=204)
def delete_resource(resource_id: int, db: Session = Depends(get_db)):
    """Delete a resource, its file, and its ChromaDB chunks."""
    resource = db.query(Resource).filter(Resource.id == resource_id).first()
    if not resource:
        raise HTTPException(status_code=404, detail="منبع یافت نشد")

    # Remove from ChromaDB
    try:
        delete_resource_chunks(resource.course_id, resource.id)
    except Exception:
        pass

    # Remove stored file
    try:
        Path(resource.stored_path).unlink(missing_ok=True)
    except Exception:
        pass

    db.delete(resource)
    db.commit()


@router.post("/resources/{resource_id}/reprocess", response_model=ResourceResponse)
def reprocess_resource(resource_id: int, db: Session = Depends(get_db)):
    """Re-parse and re-embed a resource's document."""
    resource = db.query(Resource).filter(Resource.id == resource_id).first()
    if not resource:
        raise HTTPException(status_code=404, detail="منبع یافت نشد")

    resource.status = "processing"
    db.commit()

    try:
        # Remove old chunks first
        try:
            delete_resource_chunks(resource.course_id, resource.id)
        except Exception:
            pass

        chunks = process_pdf(resource.stored_path)
        if not chunks:
            resource.status = "failed"
            db.commit()
            db.refresh(resource)
            return _serialize_resource(resource)

        chunk_count = add_document_chunks(
            course_id=resource.course_id,
            resource_id=resource.id,
            filename=resource.filename,
            chunks=chunks,
        )
        resource.status = "ready"
        resource.chunk_count = chunk_count
        db.commit()
        db.refresh(resource)
    except Exception:
        resource.status = "failed"
        db.commit()
        db.refresh(resource)

    return _serialize_resource(resource)


# ---------- Course Management ----------


@router.get("/courses", response_model=list[CourseResponse])
def list_all_courses(db: Session = Depends(get_db)):
    """List all courses (including inactive) for admin management."""
    return db.query(Course).order_by(Course.title).all()


@router.post("/courses", response_model=CourseResponse, status_code=status.HTTP_201_CREATED)
def create_course(payload: CourseCreateRequest, db: Session = Depends(get_db)):
    """Create a new course."""
    if db.query(Course).filter(Course.code == payload.code).first():
        raise HTTPException(status_code=400, detail="کد درس قبلاً ثبت شده است")

    course = Course(
        code=payload.code,
        title=payload.title,
        description=payload.description,
    )
    db.add(course)
    db.commit()
    db.refresh(course)
    return course


@router.put("/courses/{course_id}", response_model=CourseResponse)
def update_course(course_id: int, payload: CourseUpdateRequest, db: Session = Depends(get_db)):
    """Update course details or activation status."""
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="درس یافت نشد")

    if payload.code is not None and payload.code != course.code:
        if db.query(Course).filter(Course.code == payload.code).first():
            raise HTTPException(status_code=400, detail="کد درس قبلاً ثبت شده است")
        course.code = payload.code
    if payload.title is not None:
        course.title = payload.title
    if payload.description is not None:
        course.description = payload.description
    if payload.is_active is not None:
        course.is_active = payload.is_active

    db.commit()
    db.refresh(course)
    return course


@router.delete("/courses/{course_id}", status_code=204)
def delete_course(course_id: int, db: Session = Depends(get_db)):
    """Delete a course, its resources, and its ChromaDB collection."""
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="درس یافت نشد")

    # Delete Chroma collection
    try:
        delete_course_collection(course_id)
    except Exception:
        pass

    # Delete uploaded files
    course_dir = settings.upload_path / str(course_id)
    try:
        for f in course_dir.iterdir():
            f.unlink(missing_ok=True)
        course_dir.rmdir()
    except Exception:
        pass

    db.delete(course)
    db.commit()


# ---------- Course Requests ----------


@router.get("/requests", response_model=list[CourseRequestResponse])
def list_course_requests(db: Session = Depends(get_db)):
    """List all course requests."""
    return db.query(CourseRequest).order_by(CourseRequest.created_at.desc()).all()


@router.patch("/requests/{request_id}", response_model=CourseRequestResponse)
def update_course_request(request_id: int, payload: CourseRequestAdminUpdate, db: Session = Depends(get_db)):
    """Approve or reject a course request."""
    request = db.query(CourseRequest).filter(CourseRequest.id == request_id).first()
    if not request:
        raise HTTPException(status_code=404, detail="درخواست یافت نشد")

    request.status = payload.status
    if payload.admin_note is not None:
        request.admin_note = payload.admin_note

    # Auto-create the course when approved
    if payload.status == "approved":
        code = request.course_code or f"REQ-{request.id}"
        existing = db.query(Course).filter(Course.code == code).first()
        if not existing:
            course = Course(code=code, title=request.course_name, description=request.description)
            db.add(course)

    db.commit()
    db.refresh(request)
    return request


# ---------- Settings ----------


@router.get("/settings", response_model=list[SettingResponse])
def list_settings(db: Session = Depends(get_db)):
    """List all system settings."""
    return db.query(Setting).order_by(Setting.key).all()


@router.put("/settings/{key}", response_model=SettingResponse)
def update_setting(key: str, payload: SettingUpdateRequest, db: Session = Depends(get_db)):
    """Create or update a system setting (e.g. Gemini API key)."""
    setting = db.query(Setting).filter(Setting.key == key).first()
    if setting:
        setting.value = payload.value
    else:
        setting = Setting(key=key, value=payload.value)
        db.add(setting)

    db.commit()
    db.refresh(setting)
    return setting