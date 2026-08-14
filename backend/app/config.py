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
    gemini_embedding_model: str = "models/text-embedding-004"
    gemini_chat_model: str = "gemini-1.5-flash"

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