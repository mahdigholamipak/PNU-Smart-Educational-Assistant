from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import admin, auth, chat, courses, requests, users
from app.config import settings
from app.database import Base, engine
from app.models import *  # noqa: F401,F403 - ensures all models are registered

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