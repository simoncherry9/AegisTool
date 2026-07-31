"""App factory de la API FastAPI (minuta §8, §34).

Bound a 127.0.0.1 por defecto — nunca exponer fuera de localhost (minuta §34).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from aegiswifi import __version__
from aegiswifi.api.v1 import api_router
from aegiswifi.core.config import get_settings
from aegiswifi.core.exceptions import add_exception_handlers
from aegiswifi.core.logging import configure_logging, get_logger
from aegiswifi.database.engine import get_sessionmaker
from aegiswifi.jobs.event_bus import get_event_bus, reset_event_bus
from aegiswifi.jobs.manager import JobManager, reset_job_manager, set_job_manager


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging(level=get_settings().log_level, json_logs=get_settings().log_json)
    log = get_logger(__name__)
    settings = get_settings()
    log.info("aegiswifi starting", version=__version__, env=settings.environment)

    # Inicializar sistema de trabajos (JobManager + EventBus).
    event_bus = get_event_bus(buffer_size=settings.jobs.event_buffer_size)
    session_factory = get_sessionmaker()
    with session_factory() as db:
        try:
            from aegiswifi.users.service import seed_default_admin
            seed_default_admin(db)
        except Exception as exc:
            log.warning("default admin seed failed", error=str(exc))

    try:
        manager = JobManager(
            session_factory=session_factory,
            event_bus=event_bus,
            config=settings.jobs,
        )
        set_job_manager(manager)
        await manager.start()
        log.info(
            "job manager started",
            max_workers=settings.jobs.max_workers,
            heartbeat_interval=settings.jobs.heartbeat_interval,
        )
    except Exception as exc:
        log.warning("job manager skipped (common in tests/setup)", error=str(exc))

    yield

    log.info("aegiswifi shutting down — stopping job manager")
    try:  # noqa: SIM105 — suppress() no soporta await
        await manager.stop()
    except Exception:  # noqa: S110 — errores de parada ignorados durante shutdown
        pass
    reset_job_manager()
    reset_event_bus()
    log.info("job manager stopped")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="AegisWiFi",
        description="Plataforma profesional de auditoría de redes inalámbricas.",
        version=__version__,
        lifespan=lifespan,
        # §34: la API es local. Los handlers validan scopes y entrada.
        docs_url="/docs" if settings.is_dev else None,
        redoc_url=None,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router)
    add_exception_handlers(app)
    return app


app = create_app()
