"""Application-wide structured logging configuration.

Centralizes log formatting, level, and handlers so every module uses one
consistent pipeline instead of ad-hoc ``print()`` calls or mixed formats.

Typical usage::

    from app.core.logging import configure_logging, get_logger

    configure_logging()          # once, at app startup
    logger = get_logger(__name__)
    logger.info("worker started")
"""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

#: Single consistent log line format with structured fields.
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_configured = False


def configure_logging(*, level: int | str = logging.INFO, log_file: str | Path | None = None) -> None:
    """Configure the root logger with a console handler and optional rotating file handler.

    Idempotent — safe to call from tests and workers that import the app more
    than once. The first invocation wins so repeated imports never stack
    duplicate handlers.

    Args:
        level: Logging level for the root logger (defaults to ``INFO``).
        log_file: Optional path for a rotating file handler. When ``None``,
            logs go only to stdout. Rotation keeps the file bounded at 5 MB
            with up to 3 backups so production disks don't fill silently.
    """
    global _configured
    if _configured:
        return

    root = logging.getLogger()
    root.setLevel(level)

    console = logging.StreamHandler(sys.stdout)
    console.setLevel(level)
    console.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))
    root.addHandler(console)

    if log_file:
        path = Path(log_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            str(path),
            maxBytes=5 * 1024 * 1024,  # 5 MB
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))
        root.addHandler(file_handler)

    # Prevent uvicorn's default "Config object already initialized" noise from
    # duplicating our console handler for the same stream.
    root.propagate = False

    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Return a module-scoped logger that inherits the root configuration."""
    return logging.getLogger(name)