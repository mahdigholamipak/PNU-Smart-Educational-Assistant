"""FastAPI application entrypoint.

Wires together:
- Structured logging (``app.core.logging``)
- Standardized exception handlers (``app.core.exceptions``)
- Database table creation + lightweight migrations
- All API routers
"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text

from app.api import admin, auth, chat, courses, requests, users
from app.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging
from app.database import Base, engine
from app.models import (  # noqa: F401 - ensures all models are registered
    ApiUsageStats,
    ChatMessage,
    ChatSession,
    Course,
    CourseRequest,
    Resource,
    Setting,
    SystemLog,
    User,
)

logger = logging.getLogger(__name__)


def _run_lightweight_migrations() -> None:
    """Add new columns to existing SQLite tables (create_all only adds new tables)."""
    inspector = inspect(engine)
    if "resources" in inspector.get_table_names():
        columns = {col["name"] for col in inspector.get_columns("resources")}
        if "error_message" not in columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE resources ADD COLUMN error_message TEXT"))

    # Chat sessions: add updated_at for "last edited" history sorting.
    if "chat_sessions" in inspector.get_table_names():
        columns = {col["name"] for col in inspector.get_columns("chat_sessions")}
        if "updated_at" not in columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE chat_sessions ADD COLUMN updated_at DATETIME"))
                # Backfill existing rows with their created_at value.
                conn.execute(text("UPDATE chat_sessions SET updated_at = created_at WHERE updated_at IS NULL"))

    # Chat messages: add image_data so attached screenshots persist and can be
    # re-rendered as real thumbnails in the chat/history UI.
    if "chat_messages" in inspector.get_table_names():
        columns = {col["name"] for col in inspector.get_columns("chat_messages")}
        if "image_data" not in columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE chat_messages ADD COLUMN image_data TEXT"))

    # Legacy API usage table: replaced by api_usage_stats (per-key + model rows).
    # Drop the old single-model-per-key table so it never shadows the new one.
    if "api_usage" in inspector.get_table_names():
        with engine.begin() as conn:
            conn.execute(text("DROP TABLE IF EXISTS api_usage"))


def _log_startup_diagnostics() -> None:
    """Log a concise configuration summary at startup.

    Reports database engine, storage paths, cache state, CORS origins, and the
    number of configured Gemini API keys — WITHOUT ever logging the keys
    themselves. This gives operators a single "system ready" banner without
    leaking secrets.
    """
    from app.services.llm_service import resolve_api_keys

    db_display = settings.database_url
    # Mask credentials in the URL (e.g. "postgresql://user:***@host/db").
    if "://" in db_display and "@" in db_display:
        scheme, _, rest = db_display.partition("://")
        userinfo, _, host = rest.rpartition("@")
        if ":" in userinfo:
            userinfo = userinfo.split(":", 1)[0]
        db_display = f"{scheme}://{userinfo}:***@{host}"

    key_count = len(resolve_api_keys())

    logger.info("─" * 62)
    logger.info("PNU Smart Educational Assistant — startup diagnostics")
    logger.info("─" * 62)
    logger.info("Database:        %s", db_display)
    logger.info("ChromaDB dir:    %s", settings.chroma_path)
    logger.info("Uploads dir:     %s", settings.upload_path)
    logger.info("CORS origins:    %s", ", ".join(settings.cors_origin_list) or "(none)")
    logger.info("Cache enabled:   %s (embedding=%s, ocr=%s)", settings.cache_enabled, settings.embedding_cache_size, settings.ocr_cache_size)
    logger.info("Gemini keys:     %d configured", key_count)
    if key_count == 0:
        logger.warning("No Gemini API keys configured — AI features will fail until keys are added in Admin → Settings")
    logger.info("─" * 62)


# Configure structured logging once at startup.
configure_logging()

app = FastAPI(
    title="PNU Smart Educational Assistant API",
    description="RAG-based AI chat API for university students",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register standardized exception handlers (HTTP, validation, SQLAlchemy, generic).
register_exception_handlers(app)

# Create database tables on startup
Base.metadata.create_all(bind=engine)

# Apply lightweight migrations for new columns on existing tables
_run_lightweight_migrations()

# Log the configuration summary banner (DB, storage, cache, key count).
_log_startup_diagnostics()

# Register routers
app.include_router(auth.router, prefix="/api")
app.include_router(users.router, prefix="/api")
app.include_router(courses.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(requests.router, prefix="/api")
app.include_router(admin.router, prefix="/api")

# Serve built frontend (single-container deploy) if present.
from pathlib import Path as _Path
_FRONTEND_DIST = _Path(__file__).resolve().parent.parent / "frontend_dist"
if (_FRONTEND_DIST / "index.html").exists():
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import FileResponse

    app.mount("/assets", StaticFiles(directory=str(_FRONTEND_DIST / "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa(full_path: str):
        target = _FRONTEND_DIST / full_path
        if full_path and target.is_file():
            return FileResponse(target)
        return FileResponse(_FRONTEND_DIST / "index.html")


@app.get("/")
def root():
    """Health check endpoint."""
    return {"status": "ok", "app": "PNU Smart Educational Assistant"}


# One-time admin bootstrap: only active while ADMIN_SETUP_TOKEN env var is set.
# After creating the admin, remove that env var in Render to disable this route.
from pydantic import BaseModel as _BM
from fastapi import HTTPException, Depends
from app.database import SessionLocal, Base as _Base, engine as _engine
from sqlalchemy.orm import Session as _Session


class _AdminSetup(_BM):
    setup_token: str
    email: str
    password: str
    full_name: str = "مدیر سامانه"


@app.post("/api/bootstrap-admin", include_in_schema=False)
def bootstrap_admin(payload: _AdminSetup, db: _Session = Depends(_get_db)):
    import os
    expected = os.environ.get("ADMIN_SETUP_TOKEN", "")
    if not expected or payload.setup_token != expected:
        raise HTTPException(status_code=404, detail="Not found")
    from app.models import User as _User
    from app.core.security import hash_password as _hp
    if db.query(_User).filter(_User.email == payload.email).first():
        return {"ok": False, "detail": "admin already exists — remove ADMIN_SETUP_TOKEN now"}
    u = _User(email=payload.email, password_hash=_hp(payload.password),
              full_name=payload.full_name, role="admin", is_active=True)
    db.add(u)
    db.commit()
    return {"ok": True, "detail": "admin created — NOW remove ADMIN_SETUP_TOKEN env var in Render"}


def _get_db():
    from app.database import SessionLocal as _SL
    db = _SL()
    try:
        yield db
    finally:
        db.close()