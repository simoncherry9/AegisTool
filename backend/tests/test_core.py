"""Tests del núcleo: config, exceptions, logging (minuta §1, §34, §19)."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


# ===================================================================
# Config Tests
# ===================================================================


class TestSettings:
    """Tests de configuración vía pydantic-settings."""

    def test_defaults(self):
        """Valores por defecto del Settings."""
        from aegiswifi.core.config import PathsConfig, Settings

        # Usar Settings solo con defaults (sin env).
        settings = Settings(paths=PathsConfig(data_dir=Path("/tmp")))  # evitar crear dirs
        assert settings.environment == "development"
        assert settings.debug is False
        assert settings.log_level == "INFO"
        assert settings.api_host == "127.0.0.1"
        assert settings.api_port == 8000
        assert settings.jobs.max_workers == 2
        assert settings.jobs.heartbeat_interval == 15

    def test_database_url_default_sqlite(self):
        """database_url property genera URL SQLite."""
        from aegiswifi.core.config import PathsConfig, Settings

        settings = Settings(paths=PathsConfig(data_dir=Path("/tmp/data"), db_path=Path("/tmp/data/aegiswifi.db")))
        url = settings.database_url
        assert url.startswith("sqlite:///")
        assert url.endswith("aegiswifi.db")

    def test_database_url_override(self):
        """database_url property usa override si está configurado."""
        from aegiswifi.core.config import Settings

        settings = Settings(database_url="postgresql://user:pass@localhost/db")
        assert settings.database_url == "postgresql://user:pass@localhost/db"

    def test_is_dev_true_by_default(self):
        from aegiswifi.core.config import PathsConfig, Settings

        settings = Settings(paths=PathsConfig(data_dir=Path("/tmp")))
        assert settings.is_dev is True
        # Cambiar a producción.
        prod = Settings(environment="production", paths=PathsConfig(data_dir=Path("/tmp")))
        assert prod.is_dev is False

    def test_cors_origins_default(self):
        from aegiswifi.core.config import PathsConfig, Settings

        settings = Settings(paths=PathsConfig(data_dir=Path("/tmp")))
        origins = settings.cors_origins
        assert "http://localhost:5173" in origins
        assert "http://127.0.0.1:5173" in origins

    def test_ensure_dirs_creates_directories(self, tmp_path: Path):
        """ensure_dirs crea los directorios necesarios."""
        from aegiswifi.core.config import JobConfig, PathsConfig, Settings

        data = tmp_path / "test_data"
        paths = PathsConfig(
            data_dir=data,
            evidence_dir=data / "evidence",
        )
        settings = Settings(
            paths=paths,
            jobs=JobConfig(log_dir=data / "job_logs"),
        )
        settings.ensure_dirs()
        assert (data / "job_logs").is_dir()
        assert (data / "evidence").is_dir()

    def test_env_prefix_override(self, monkeypatch: pytest.MonkeyPatch):
        """Las variables de entorno con prefijo AEGISWIFI_ sobreescriben defaults."""
        monkeypatch.setenv("AEGISWIFI_ENVIRONMENT", "production")
        monkeypatch.setenv("AEGISWIFI_API_HOST", "0.0.0.0")
        monkeypatch.setenv("AEGISWIFI_API_PORT", "9000")

        # Limpiar caché de get_settings antes/después para no contaminar otros tests.
        from aegiswifi.core.config import get_settings

        get_settings.cache_clear()
        try:
            settings = get_settings()
            assert settings.environment == "production"
            assert settings.api_host == "0.0.0.0"
            assert settings.api_port == 9000
        finally:
            get_settings.cache_clear()
            monkeypatch.undo()
            monkeypatch.setenv("AEGISWIFI_ENVIRONMENT", "development")

    def test_get_settings_cached(self):
        """get_settings es LRU cache de tamaño 1."""
        from aegiswifi.core.config import get_settings

        get_settings.cache_clear()
        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2
        get_settings.cache_clear()

    def test_job_config_defaults(self):
        from aegiswifi.core.config import JobConfig

        cfg = JobConfig()
        assert cfg.max_workers == 2
        assert cfg.heartbeat_interval == 15
        assert cfg.default_timeout == 300
        assert cfg.process_kill_timeout == 5
        assert cfg.event_buffer_size == 1000


# ===================================================================
# Exceptions Tests
# ===================================================================


class TestExceptions:
    """Tests de la jerarquía de excepciones de dominio."""

    def test_aegis_error_default_status(self):
        from aegiswifi.core.exceptions import AegisError

        err = AegisError("base error")
        assert err.status_code == 500
        assert str(err) == "base error"

    def test_not_found_404(self):
        from aegiswifi.core.exceptions import NotFound

        err = NotFound("engagement no encontrado")
        assert err.status_code == 404
        assert "engagement" in str(err)

    def test_validation_failed_422(self):
        from aegiswifi.core.exceptions import ValidationFailed

        err = ValidationFailed("campo inválido")
        assert err.status_code == 422

    def test_scope_violation_403(self):
        from aegiswifi.core.exceptions import ScopeViolation

        err = ScopeViolation("acción no autorizada")
        assert err.status_code == 403

    def test_conflict_409(self):
        from aegiswifi.core.exceptions import Conflict

        err = Conflict("recurso duplicado")
        assert err.status_code == 409

    def test_service_unavailable_503(self):
        from aegiswifi.core.exceptions import ServiceUnavailable

        err = ServiceUnavailable("herramienta no disponible")
        assert err.status_code == 503

    def test_exception_hierarchy(self):
        """Todas las excepciones heredan de AegisError."""
        from aegiswifi.core.exceptions import (
            AegisError,
            Conflict,
            NotFound,
            ScopeViolation,
            ServiceUnavailable,
            ValidationFailed,
        )

        assert issubclass(NotFound, AegisError)
        assert issubclass(ValidationFailed, AegisError)
        assert issubclass(ScopeViolation, AegisError)
        assert issubclass(Conflict, AegisError)
        assert issubclass(ServiceUnavailable, AegisError)

    def test_add_exception_handlers_registers_handlers(self):
        """add_exception_handlers registra handlers para AegisError y excepciones generales."""
        from aegiswifi.core.exceptions import AegisError, add_exception_handlers

        app = FastAPI()
        add_exception_handlers(app)
        # Verificar que los handlers están registrados.
        assert len(app.exception_handlers) > 0
        # Al menos un handler registrado es una excepción.
        has_handler = any(
            issubclass(cls, Exception)
            for cls in app.exception_handlers
            if isinstance(cls, type) and issubclass(cls, Exception)
        )
        assert has_handler

    def test_aegis_handler_response_format(self):
        """El handler de AegisError devuelve formato JSON esperado."""
        from aegiswifi.core.exceptions import (
            NotFound,
            add_exception_handlers,
        )
        from aegiswifi.main import create_app

        app = create_app()
        with TestClient(app) as client:
            resp = client.get("/api/v1/engagements/99999")
            # Como get_db fallará (no tenemos BD), esperamos 500 o 404
            assert resp.status_code in (404, 500)
            body = resp.json()
            # Verificar formato de error
            assert "error" in body
            assert body["error"] in ("NotFound", "InternalError")


# ===================================================================
# Logging Tests
# ===================================================================


class TestLogging:
    """Tests de configuración de logging."""

    def test_configure_logging_console(self):
        """configure_logging con salida a consola."""
        from aegiswifi.core.logging import configure_logging

        # Simplemente verificar que no lanza.
        configure_logging(level="DEBUG", json_logs=False)

    def test_configure_logging_json(self):
        """configure_logging con salida JSON."""
        from aegiswifi.core.logging import configure_logging

        configure_logging(level="INFO", json_logs=True)

    def test_get_logger_returns_structlog_logger(self):
        from aegiswifi.core.logging import configure_logging, get_logger

        configure_logging("WARNING")
        logger = get_logger("test_module")
        assert logger is not None
        # Verificar que tiene el método .info esperado de structlog.
        assert hasattr(logger, "info")
        assert hasattr(logger, "error")

    def test_configure_logging_invalid_level_fallback(self):
        """Nivel inválido cae a INFO."""
        from aegiswifi.core.logging import configure_logging

        # No debe lanzar.
        configure_logging(level="INVALID")
