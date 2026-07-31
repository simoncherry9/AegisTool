"""Application configuration (minuta §9.1 backend, §34 seguridad).

Configuración resuelta, en orden de precedencia:
  1. Variables de entorno (prefijo ``AEGISWIFI_``, delimitador de anidación ``__``).
  2. ``.env`` en la raíz del repositorio.
  3. Valores por defecto definidos aquí.

El formato del archivo de alcance/autorización (``config.example.yaml``) lo parsea
:mod:`aegiswifi.scope.parser`; este módulo solo guarda ajustes de la *aplicación*.
"""

from __future__ import annotations

import secrets
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/aegiswifi/core/config.py -> parents[3] = raíz del repositorio.
REPO_ROOT = Path(__file__).resolve().parents[3]


class PathsConfig(BaseModel):
    """Ubicaciones en disco para datos, evidencia y la base SQLite."""

    data_dir: Path = REPO_ROOT / "data"
    evidence_dir: Path = REPO_ROOT / "data" / "evidence"
    db_path: Path = REPO_ROOT / "data" / "aegiswifi.db"


class SecurityConfig(BaseModel):
    """Ajustes de seguridad (minuta §19 protección de secretos, §34)."""

    require_auth: bool = True
    secret_key: str = Field(default_factory=lambda: secrets.token_urlsafe(32), repr=False)
    # Clave Fernet en base64 para cifrar secretos en reposo. Si está vacío se
    # genera/persiste automáticamente en paths.data_dir/.aegis_key (ver core.security).
    encryption_key_b64: str | None = Field(default=None, repr=False)


class JobConfig(BaseModel):
    """Ajustes del sistema de trabajos (minuta §26)."""

    max_workers: int = Field(default=2, ge=1, le=16)
    heartbeat_interval: int = Field(default=15, ge=5, le=120)
    default_timeout: int = Field(default=300, ge=30, le=86400)
    max_log_lines_memory: int = Field(default=10000, ge=100)
    event_buffer_size: int = Field(default=1000, ge=50, le=50000)
    log_dir: Path = Field(default_factory=lambda: REPO_ROOT / "data" / "job_logs")
    process_kill_timeout: int = Field(default=5, ge=1, le=30)
    evidence_dir: Path = Field(default_factory=lambda: REPO_ROOT / "data" / "evidence")


class Settings(BaseSettings):
    """Ajustes raíz. Usar :func:`get_settings` (cacheado en el proceso)."""

    model_config = SettingsConfigDict(
        env_prefix="AEGISWIFI_",
        env_nested_delimiter="__",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: str = "development"  # development | production
    debug: bool = False
    log_level: str = "INFO"
    log_json: bool = False
    # Pillado de §34: la API vive en localhost por defecto.
    api_host: str = "127.0.0.1"
    api_port: int = 8001
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"]
    )

    # Vacío => se deriva de paths.db_path (SQLite). Para PostgreSQL (futura fase):
    # "postgresql+psycopg://aegiswifi:secret@localhost/aegiswifi".
    database_url_override: str | None = Field(default=None, alias="database_url")

    paths: PathsConfig = Field(default_factory=PathsConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    jobs: JobConfig = Field(default_factory=JobConfig)

    @property
    def database_url(self) -> str:
        if self.database_url_override:
            return self.database_url_override
        return f"sqlite:///{self.paths.db_path.as_posix()}"

    @property
    def is_dev(self) -> bool:
        return self.environment == "development"

    def ensure_dirs(self) -> None:
        self.paths.data_dir.mkdir(parents=True, exist_ok=True)
        self.paths.evidence_dir.mkdir(parents=True, exist_ok=True)
        self.jobs.log_dir.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Devuelve la instancia cacheada de Settings, creando los directorios runtime."""
    settings = Settings()
    settings.ensure_dirs()
    return settings
