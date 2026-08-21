from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    database_url: str = f"sqlite:///{BASE_DIR / 'pnu_assistant.db'}"
    # Connection pool tuning (used for PostgreSQL/MySQL; SQLite uses StaticPool).
    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_pool_recycle: int = 1800

    # JWT
    jwt_secret_key: str = "change-this-to-a-long-random-secret"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 1440

    # ChromaDB
    chroma_persist_dir: str = str(BASE_DIR / "chroma_db")

    # Uploads
    upload_dir: str = str(BASE_DIR / "uploads")

    # CORS
    cors_origins: str = "http://localhost:5173"

    # Gemini
    gemini_api_key: str = ""
    gemini_embedding_model: str = "models/gemini-embedding-2"
    gemini_chat_model: str = "gemini-3.5-flash-lite"
    gemini_rewrite_model: str = "gemini-3.5-flash-lite"
    gemini_ocr_model: str = "gemini-3.5-flash-lite"

    # Embedding pipeline tuning (rate-limit resiliency)
    # Number of chunks sent per embedding API call (batchEmbedContents).
    # Each request counts as 1 against the per-key RPM budget.
    embedding_batch_size: int = 20
    # Seconds a key is "burned" after hitting a 429 (skipped by the pool).
    embedding_key_cooldown: int = 60
    # Base delay (seconds) for exponential backoff when all keys are cooling.
    embedding_backoff_base: float = 10.0
    # Maximum number of retry attempts for a single embedding batch.
    embedding_max_retries: int = 5
    # Short sleep (seconds) between successive batches to avoid spiking RPM.
    embedding_inter_batch_delay: float = 0.5

    # Semantic/LRU caching (Phase 3 — cost & token management)
    # Master switch for all in-memory caches (embedding vectors, OCR text).
    cache_enabled: bool = True
    # Max entries in the embedding LRU cache (per (query, model) key).
    embedding_cache_size: int = 512
    # Max entries in the OCR LRU cache (keyed by SHA-256 of the image bytes).
    ocr_cache_size: int = 128

    # Directories
    @property
    def upload_path(self) -> Path:
        return Path(self.upload_dir)

    @property
    def chroma_path(self) -> Path:
        return Path(self.chroma_persist_dir)

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()