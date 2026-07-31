"""Health checks (minuta §37 Fase 1 — criterio: la app transmite y persiste)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from aegiswifi import __version__
from aegiswifi.core.config import get_settings
from aegiswifi.database.engine import get_db

router = APIRouter(prefix="/health", tags=["health"])


@router.get("", status_code=status.HTTP_200_OK)
def health(db: Session = Depends(get_db)) -> dict[str, object]:
    """Liveness: versión, entorno y ping a la base de datos."""
    db_ok = True
    try:
        db.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001 — health no debe propagar errores
        db_ok = False
    settings = get_settings()
    return {
        "status": "ok" if db_ok else "degraded",
        "version": __version__,
        "environment": settings.environment,
        "database": "ok" if db_ok else "error",
        "api_bound": f"{settings.api_host}:{settings.api_port}",
    }
