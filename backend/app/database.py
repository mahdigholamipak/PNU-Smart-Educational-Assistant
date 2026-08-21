"""SQLAlchemy engine, session factory, and FastAPI dependency.

Production-hardened connection configuration:

- ``pool_pre_ping=True`` — verifies connections are alive before borrowing
  them from the pool, eliminating "server closed connection" errors after
  idle periods or database restarts.
- SQLite (local dev): pinned to ``NullPool`` with ``check_same_thread=False``.
  ``NullPool`` opens a fresh connection per session checkout, so no connection
  is ever shared between concurrent FastAPI worker threads. This is the
  canonical pattern for SQLite + FastAPI threadpool concurrency — a shared
  ``StaticPool`` connection would be used by two threads simultaneously and
  raise ``sqlite3.InterfaceError: bad parameter or other API misuse``.
- PostgreSQL/MySQL (production): explicit ``pool_size`` / ``max_overflow``
  tunables via settings so the app never exhausts the database's connection
  budget under load.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import NullPool

from app.config import settings

_is_sqlite = settings.database_url.startswith("sqlite")

if _is_sqlite:
    engine = create_engine(
        settings.database_url,
        connect_args={"check_same_thread": False},
        poolclass=NullPool,
        pool_pre_ping=True,
    )
else:
    engine = create_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_recycle=settings.db_pool_recycle,
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Base class for all ORM models."""


def get_db():
    """FastAPI dependency that yields a database session and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()