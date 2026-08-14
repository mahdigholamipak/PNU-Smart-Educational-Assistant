import json
import uuid
from pathlib import Path

import requests
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.config import settings
from app.core.deps import require_admin
from app.database import get_db
from app.models import Course, CourseRequest, Resource, Setting, SystemLog, User
from app.schemas.course import CourseCreateRequest, CourseResponse, CourseUpdateRequest
from app.schemas.request import CourseRequestAdminUpdate, CourseRequestResponse
from app.schemas.resource import ResourceResponse, SettingResponse, SettingUpdateRequest
from app.schemas.user import PublicUserResponse
from app.services.document_service import process_pdf
from app.services.llm_service import (
    get_embedding_function,
    normalize_model_name,
    resolve_api_key,
    resolve_api_keys,
)
from app.services.log_service import log_event
from app.services.vector_store import (
    add_document_chunks,
    delete_course_collection,
    delete_resource_chunks,
    get_resource_chunks,
    update_chunk_content,
)

router = APIRouter(prefix="/admin", tags=["Admin"], dependencies=[Depends(require_admin)])


def _serialize_resource(resource: Resource, course_title: str | None = None) -> ResourceResponse:
    return ResourceResponse(
        id=resource.id,
        course_id=resource.course_id,
        course_title=course_title or (resource.course.title if resource.course else None),
        filename=resource.filename,
        status=resource.status,
        chunk_count=resource.chunk_count,
        error_message=resource.error_message,
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
            resource.error_message = "متنی از فایل PDF استخراج نشد (ممکن است اسکن شده یا بدون متن باشد)."
            log_event(db, "error", "upload", f"استخراج متن از PDF ناموفق بود: {resource.filename}", f"No text extracted from {stored_path}", resource.id)
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
        resource.error_message = None
        db.commit()
        db.refresh(resource)
        log_event(
            db, "info", "upload",
            f"فایل با موفقیت پردازش شد: {resource.filename}",
            f"{chunk_count} chunk(s) embedded for course {course_id}",
            resource.id,
        )
    except Exception as exc:
        resource.status = "failed"
        resource.error_message = str(exc)[:500]
        log_event(
            db, "error", "upload",
            f"خطا در پردازش فایل: {resource.filename}",
            str(exc),
            resource.id,
        )
        db.commit()
        db.refresh(resource)

    return _serialize_resource(resource, course.title)


@router.delete("/resources/{resource_id}", status_code=204)
def delete_resource(resource_id: int, db: Session = Depends(get_db)):
    """Delete a resource, its file, and its ChromaDB chunks."""
    resource = db.query(Resource).filter(Resource.id == resource_id).first()
    if not resource:
        raise HTTPException(status_code=404, detail="منبع یافت نشد")

    filename = resource.filename

    # Remove from ChromaDB
    try:
        delete_resource_chunks(resource.course_id, resource.id)
    except Exception as exc:
        log_event(
            db, "error", "vector_store",
            f"خطا در حذف chunkهای وکتوری: {filename}",
            str(exc),
            resource.id,
        )

    # Remove stored file + empty course dir
    try:
        stored = Path(resource.stored_path)
        if stored.exists():
            stored.unlink()
        course_dir = stored.parent
        try:
            course_dir.rmdir()
        except OSError:
            pass
    except Exception as exc:
        log_event(
            db, "error", "system",
            f"خطا در حذف فایل ذخیره‌شده: {filename}",
            str(exc),
            resource.id,
        )

    db.delete(resource)
    db.commit()
    log_event(
        db, "info", "system",
        f"منبع حذف شد: {filename}",
        f"resource_id={resource_id}, course_id={resource.course_id}",
        resource_id,
    )


@router.post("/resources/{resource_id}/reprocess", response_model=ResourceResponse)
def reprocess_resource(resource_id: int, db: Session = Depends(get_db)):
    """Re-parse and re-embed a resource's document."""
    resource = db.query(Resource).filter(Resource.id == resource_id).first()
    if not resource:
        raise HTTPException(status_code=404, detail="منبع یافت نشد")

    resource.status = "processing"
    resource.error_message = None
    db.commit()

    try:
        # Remove old chunks first
        try:
            delete_resource_chunks(resource.course_id, resource.id)
        except Exception as exc:
            log_event(
                db, "error", "vector_store",
                f"خطا در حذف chunkهای قبلی برای: {resource.filename}",
                str(exc),
                resource.id,
            )

        chunks = process_pdf(resource.stored_path)
        if not chunks:
            resource.status = "failed"
            resource.error_message = "متنی از فایل PDF استخراج نشد."
            log_event(db, "error", "reprocess", f"پردازش مجدد ناموفق بود (بدون متن): {resource.filename}", resource_id=resource.id)
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
    except Exception as exc:
        resource.status = "failed"
        resource.error_message = str(exc)[:500]
        log_event(
            db, "error", "reprocess",
            f"پردازش مجدد ناموفق بود: {resource.filename}",
            str(exc),
            resource.id,
        )
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


# ---------- System Logs (Task 3) ----------


@router.get("/logs")
def list_logs(limit: int = 100, level: str | None = None, db: Session = Depends(get_db)):
    """List system logs (newest first), optionally filtered by level."""
    query = db.query(SystemLog).order_by(SystemLog.created_at.desc())
    if level and level in ("info", "warning", "error"):
        query = query.filter(SystemLog.level == level)
    logs = query.limit(min(limit, 500)).all()
    return [
        {
            "id": log.id,
            "level": log.level,
            "source": log.source,
            "message": log.message,
            "details": log.details,
            "resource_id": log.resource_id,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        }
        for log in logs
    ]


@router.delete("/logs", status_code=204)
def clear_logs(db: Session = Depends(get_db)):
    """Delete all system logs."""
    db.query(SystemLog).delete()
    db.commit()


# ---------- Gemini Models & Test Connection (Task 4) ----------


def _fetch_models_with_keys(api_keys: list[str], db: Session) -> dict:
    """Fetch the Gemini model list using the first key that works.

    Iterates over all configured keys so that an invalid/rate-limited first key
    doesn't block model loading when additional keys are available.
    """
    last_error = ""
    for api_key in api_keys:
        try:
            resp = requests.get(
                "https://generativelanguage.googleapis.com/v1beta/models",
                params={"key": api_key},
                timeout=15,
            )
            if resp.status_code in (400, 401, 403):
                last_error = "کلید API نامعتبر است یا دسترسی ندارد."
                continue
            resp.raise_for_status()
            return resp.json()
        except HTTPException:
            raise
        except Exception as exc:
            last_error = str(exc)
            continue
    raise HTTPException(status_code=502, detail=last_error or "خطا در ارتباط با سرویس Gemini.")


@router.get("/gemini/models")
def list_gemini_models(db: Session = Depends(get_db)):
    """Fetch available Gemini models using the saved API key(s), split by capability."""
    api_keys = resolve_api_keys()
    if not api_keys:
        raise HTTPException(status_code=400, detail="کلید API تنظیم نشده است. ابتدا کلید را ذخیره کنید.")

    data = _fetch_models_with_keys(api_keys, db)

    chat_models = []
    embedding_models = []
    for model in data.get("models", []):
        name = model.get("name", "")  # e.g. "models/gemini-1.5-flash"
        if not name:
            continue
        supported = model.get("supportedGenerationMethods", []) or []
        display = name.replace("models/", "")
        if "generateContent" in supported:
            chat_models.append({"id": name, "display": display})
        if "embedContent" in supported:
            embedding_models.append({"id": name, "display": display})

    return {"chat_models": chat_models, "embedding_models": embedding_models}


@router.post("/gemini/test-connection")
def test_gemini_connection(payload: dict, db: Session = Depends(get_db)):
    """Verify the API key(s) and chosen models work (chat + embedding ping).

    Supports multiple API keys (comma/newline separated). Iterates over all keys
    and succeeds if at least one key can validate both the chat and embedding
    models. Returns accurate feedback distinguishing invalid keys from
    model-specific failures, including HTTP status codes.
    """
    raw_keys = (payload.get("api_key") or "").strip() or ""
    if raw_keys:
        api_keys = [k.strip() for k in raw_keys.replace("\n", ",").split(",") if k.strip()]
    else:
        api_keys = resolve_api_keys()
    chat_model = (payload.get("chat_model") or "").strip() or None
    embedding_model = (payload.get("embedding_model") or "").strip() or None

    if not api_keys:
        raise HTTPException(status_code=400, detail="کلید API وارد نشده است.")

    # Normalize model names (strip "models/" prefix) so REST paths are correct
    chat_model = normalize_model_name(chat_model) if chat_model else None
    embedding_model = normalize_model_name(embedding_model) if embedding_model else None

    # Try each key until one validates both models
    last_chat_error = ""
    last_embed_error = ""
    for api_key in api_keys:
        # 1. Verify key + fetch models
        try:
            resp = requests.get(
                "https://generativelanguage.googleapis.com/v1beta/models",
                params={"key": api_key},
                timeout=15,
            )
            if resp.status_code in (400, 401, 403):
                continue  # invalid key, try next
            resp.raise_for_status()
            models_data = resp.json()
        except HTTPException:
            raise
        except Exception as exc:
            log_event(db, "error", "gemini", "خطا در تست ارتباط (لیست مدل‌ها)", str(exc))
            continue

        available = {m.get("name", "").replace("models/", ""): m for m in models_data.get("models", [])}

        # 2. Ping chat model (with fallback to first available chat model)
        if not chat_model:
            chat_model = next((m for m in available if "generateContent" in (available[m].get("supportedGenerationMethods") or [])), None)
        chat_ok = False
        chat_error = ""
        if chat_model:
            try:
                ping_resp = requests.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{chat_model}:generateContent",
                    params={"key": api_key},
                    json={"contents": [{"parts": [{"text": "سلام"}]}]},
                    timeout=15,
                )
                chat_ok = ping_resp.status_code == 200
                if not chat_ok:
                    chat_error = f" (HTTP {ping_resp.status_code})"
            except Exception as exc:
                chat_ok = False
                chat_error = f" ({type(exc).__name__})"

        # 3. Ping embedding model (with fallback to first available embedding model)
        if not embedding_model:
            embedding_model = next((m for m in available if "embedContent" in (available[m].get("supportedGenerationMethods") or [])), None)
        embed_ok = False
        embed_error = ""
        if embedding_model:
            try:
                embed_resp = requests.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{embedding_model}:embedContent",
                    params={"key": api_key},
                    json={"content": {"parts": [{"text": "تست"}]}},
                    timeout=15,
                )
                embed_ok = embed_resp.status_code == 200
                if not embed_ok:
                    embed_error = f" (HTTP {embed_resp.status_code})"
            except Exception as exc:
                embed_ok = False
                embed_error = f" ({type(exc).__name__})"

        if chat_ok and embed_ok:
            log_event(db, "info", "gemini", "تست ارتباط با موفقیت انجام شد", f"chat={chat_model}, embed={embedding_model}")
            return {"ok": True, "chat_model": chat_model, "embedding_model": embedding_model}

        # Record the last failure for accurate feedback
        if not chat_ok:
            last_chat_error = f"مدل گفتگو ({chat_model}) قابل استفاده نیست{chat_error}"
        if not embed_ok:
            last_embed_error = f"مدل بردارساز ({embedding_model}) قابل استفاده نیست{embed_error}"

    # All keys failed
    reason = []
    if last_chat_error:
        reason.append(last_chat_error)
    if last_embed_error:
        reason.append(last_embed_error)
    if not reason:
        reason.append("هیچ‌کدام از کلیدهای API معتبر نیستند یا دسترسی ندارند.")
    log_event(db, "warning", "gemini", "تست ارتباط ناموفق بود", "؛ ".join(reason))
    raise HTTPException(status_code=400, detail="تست ناموفق بود: " + "؛ ".join(reason))


# ---------- Chunk Viewer & Editor (Task 8) ----------


@router.get("/resources/{resource_id}/chunks")
def list_resource_chunks(resource_id: int, db: Session = Depends(get_db)):
    """Return all vector chunks for a resource (for admin inspection/editing)."""
    resource = db.query(Resource).filter(Resource.id == resource_id).first()
    if not resource:
        raise HTTPException(status_code=404, detail="منبع یافت نشد")

    chunks = get_resource_chunks(resource.course_id, resource.id)
    return {"resource_id": resource.id, "filename": resource.filename, "chunks": chunks}


@router.put("/resources/chunks/{chunk_id}")
def edit_resource_chunk(chunk_id: str, payload: dict, db: Session = Depends(get_db)):
    """Edit a chunk's text and re-embed it so vector search stays in sync."""
    new_content = (payload.get("content") or "").strip()
    if not new_content:
        raise HTTPException(status_code=400, detail="متن قطعه نمی‌تواند خالی باشد.")

    # Find the resource this chunk belongs to (chunk id format: res_{resource_id}_chunk_{i})
    parts = chunk_id.split("_")
    if len(parts) < 3 or not parts[1].isdigit():
        raise HTTPException(status_code=400, detail="شناسه قطعه نامعتبر است.")
    resource_id = int(parts[1])

    resource = db.query(Resource).filter(Resource.id == resource_id).first()
    if not resource:
        raise HTTPException(status_code=404, detail="منبع یافت نشد")

    try:
        embedding_fn = get_embedding_function()
        update_chunk_content(resource.course_id, chunk_id, new_content, embedding_fn)
    except Exception as exc:
        log_event(
            db, "error", "vector_store",
            f"خطا در بردارسازی مجدد قطعه: {chunk_id}",
            str(exc),
            resource.id,
        )
        raise HTTPException(status_code=500, detail="خطا در بردارسازی مجدد قطعه. جزئیات در لاگ سیستم ثبت شد.")

    log_event(
        db, "info", "vector_store",
        f"قطعه ویرایش و بردارسازی شد: {chunk_id}",
        resource_id=resource.id,
    )
    return {"ok": True, "chunk_id": chunk_id}
