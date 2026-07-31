"""Fixtures de test: BD SQLite en memoria + TestClient + override de settings."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Forzar entorno de test ANTES de importar aegiswifi: SQLite en memoria y sin
# clave de cifrado configurada (se autogenera en directorio temporal).
os.environ.setdefault("AEGISWIFI_ENVIRONMENT", "development")
os.environ.setdefault("AEGISWIFI_DATABASE__URL", "")
os.environ.setdefault("AEGISWIFI_SECURITY__REQUIRE_AUTH", "false")

from aegiswifi.core.logging import configure_logging  # noqa: E402
from aegiswifi.database import models  # noqa: E402,F401
from aegiswifi.database.base import Base  # noqa: E402
from aegiswifi.database.engine import dispose_engine, get_db  # noqa: E402
from aegiswifi.main import app  # noqa: E402


@pytest.fixture()
def db_session():
    """Sesión contra SQLite en memoria, aislada por test."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
    session = SessionLocal()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture()
def client(db_session):
    """TestClient de la API con la dependencia get_db parcheada a `db_session`."""
    configure_logging("WARNING", json_logs=False)

    def _override():
        yield db_session

    app.dependency_overrides[get_db] = _override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def _reset_engine_singleton():
    """Evita que el engine real (SQLite en disco) contamine entre tests."""
    dispose_engine()
    yield
    dispose_engine()
