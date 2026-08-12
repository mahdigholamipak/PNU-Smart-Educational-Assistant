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