"""Excepciones de dominio y handlers de FastAPI (minuta §34, gestión de errores)."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from structlog import get_logger


class AegisError(Exception):
    """Base de todos los errores de dominio de AegisWiFi."""

    status_code: int = 500


class NotFound(AegisError):
    status_code = 404


class ValidationFailed(AegisError):
    status_code = 422


class ScopeViolation(AegisError):
    """Se lanza cuando una acción queda fuera del alcance autorizado (minuta §12)."""

    status_code = 403


class Conflict(AegisError):
    status_code = 409


class ServiceUnavailable(AegisError):
    """El servicio o recurso solicitado no está disponible."""

    status_code = 503


def add_exception_handlers(app: FastAPI) -> None:
    """Registra los handlers de error en la aplicación."""

    @app.exception_handler(AegisError)
    async def _aegis_handler(request: Request, exc: AegisError) -> JSONResponse:
        log = get_logger(__name__)
        log.warning(
            "aegis_error",
            error=type(exc).__name__,
            path=request.url.path,
            detail=str(exc),
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": type(exc).__name__, "detail": str(exc) or None},
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={"error": "ValidationError", "detail": exc.errors()},
        )

    @app.exception_handler(Exception)
    async def _unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
        log = get_logger(__name__)
        log.exception("unhandled_error", path=request.url.path)
        return JSONResponse(
            status_code=500,
            content={"error": "InternalError", "detail": None},
        )
