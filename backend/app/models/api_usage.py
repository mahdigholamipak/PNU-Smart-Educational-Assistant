from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ApiUsage(Base):
    """Aggregated usage statistics per API key.

    Tracks how many requests and tokens each (masked) API key has consumed so
    admins can monitor rate-limit pressure and per-key consumption.
    """

    __tablename__ = "api_usage"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    api_key_masked: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    total_requests: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    total_tokens_used: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )