from typing import Any

from sqlalchemy.orm import Session

from app.models import SystemLog


def log_event(
    db: Session,
    level: str = "info",
    source: str = "system",
    message: str = "",
    details: str | None = None,
    resource_id: int | None = None,
    commit: bool = True,
) -> SystemLog:
    """Persist a system log entry. Levels: info | warning | error."""
    entry = SystemLog(
        level=level,
        source=source,
        message=message,
        details=(details or "")[:5000],
        resource_id=resource_id,
    )
    db.add(entry)
    if commit:
        db.commit()
    return entry