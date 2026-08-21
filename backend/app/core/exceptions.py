"""Standardized HTTP exception handlers for the FastAPI application.

Centralizes error responses so the frontend always receives a consistent
``{detail: str}`` envelope (FastAPI's conventional shape) instead of
framework-default or ad-hoc payloads. This also guarantees that unexpected
exceptions are logged with full stack traces and never leak internals.

Wired into the app in ``app.main`` via ``app.add_exception_handler``.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


def _json_response(status_code: int, detail: str) -> JSONResponse:
    """Build a consistent JSON error envelope."""
    return JSONResponse(status_code=status_code, content={"detail": detail})


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Return the standard ``{detail: str}`` body for any HTTPException."""
    return _json_response(exc.status_code, str(exc.detail))


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Return a readable Persian-friendly message for Pydantic validation errors.

    Surfaces the first field error as the primary message while keeping the
    full error list available for debugging inside the server logs.
    """
    errors = exc.errors()
    first = errors[0] if errors else {}
    loc = ".".join(str(part) for part in first.get("loc", []) if part not in ("body", "query"))
    msg = first.get("msg", "خطای اعتبارسنجی")
    detail = f"خطای اعتبارسنجی در فیلد «{loc}»: {msg}" if loc else f"خطای اعتبارسنجی: {msg}"
    logger.warning("Validation error: %s (loc=%s)", msg, loc)
    return _json_response(status.HTTP_422_UNPROCESSABLE_ENTITY, detail)


async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    """Return a safe 500 for database errors after logging the real cause."""
    logger.exception("Unhandled SQLAlchemy error on %s %s: %s", request.method, request.url.path, exc)
    return _json_response(
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        "خطای داخلی پایگاه داده. لطفاً بعداً دوباره تلاش کنید.",
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Last-resort handler: log the stack trace and return a safe 500."""
    logger.exception("Unhandled exception on %s %s: %s", request.method, request.url.path, exc)
    return _json_response(
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        "خطای غیرمنتظره سرور. جزئیات در لاگ سیستم ثبت شد.",
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Attach all exception handlers to the FastAPI app."""
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    # SQLAlchemyError must be registered before Exception so it takes precedence.
    app.add_exception_handler(SQLAlchemyError, sqlalchemy_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)