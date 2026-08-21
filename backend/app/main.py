from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text

from app.api import admin, auth, chat, courses, requests, users
from app.config import settings
from app.database import Base, engine
from app.models import *  # noqa: F401,F403 - ensures all models are registered


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

# Create database tables on startup
Base.metadata.create_all(bind=engine)

# Apply lightweight migrations for new columns on existing tables
_run_lightweight_migrations()

# Register routers
app.include_router(auth.router, prefix="/api")
app.include_router(users.router, prefix="/api")
app.include_router(courses.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(requests.router, prefix="/api")
app.include_router(admin.router, prefix="/api")


@app.get("/")
def root():
    """Health check endpoint."""
    return {"status": "ok", "app": "PNU Smart Educational Assistant"}