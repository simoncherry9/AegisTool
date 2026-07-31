"""Engine + gestión de sesiones (SQLAlchemy 2, sincrono; SQLite por defecto).

Sync fue elegido para el núcleo: las herramientas Wi-Fi son subprocess y la cola
de jobs gestionará su propio worker. Cuando se introduzca el sistema de jobs
(Fase 1 completa) se evalúa un path async aquí.
"""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from aegiswifi.core.config import get_settings

_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_engine(settings.database_url, future=True, echo=settings.debug)
    return _engine


def get_sessionmaker() -> sessionmaker[Session]:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            bind=get_engine(), autoflush=False, expire_on_commit=False, future=True
        )
    return _SessionLocal


def get_db() -> Iterator[Session]:
    """Dependencia FastAPI: cede una sesión de base de datos."""
    session = get_sessionmaker()()
    try:
        yield session
    finally:
        session.close()


def dispose_engine() -> None:
    """Libera el engine (útil en tests y al cerrar el proceso)."""
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionLocal = None
