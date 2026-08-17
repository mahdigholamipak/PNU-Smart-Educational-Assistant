from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ApiUsageStats(Base):
    """Aggregated usage statistics per API key *and* model.

    Tracks how many requests and tokens each (masked) API key has consumed for
    each specific model. The unique constraint on ``(api_key_masked, model)``
    ensures one key used by multiple models (e.g. ``gemini-flash`` chat and
    ``gemini-embedding``) records each model's usage in its own row instead of
    overwriting the other, enabling the per-model monitoring dashboard.
    """

    __tablename__ = "api_usage_stats"
    __table_args__ = (
        UniqueConstraint(
            "api_key_masked",
            "model",
            name="uq_api_key_model",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    api_key_masked: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    total_requests: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    total_tokens_used: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )