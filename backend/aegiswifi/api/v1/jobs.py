"""Router REST + WebSocket del sistema de trabajos (minuta §26, req 13).

REST endpoints:
  GET/POST   /jobs              — listar / crear
  GET/PATCH  /jobs/{id}         — obtener / actualizar
  POST       /jobs/{id}/cancel  — cancelar
  POST       /jobs/{id}/retry   — reintentar
  GET        /jobs/{id}/events  — historial de eventos
  GET        /jobs/queue/status — métricas del manager

WebSocket:
  WS /api/v1/ws/jobs — recibe eventos del EventBus en tiempo real.
    Query params opcionales: job_id, engagement_id (filtro).
    Al conectar, envía replay de eventos relevantes como ``{"type":"replay",...}``.
"""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy.orm import Session

from aegiswifi.core.exceptions import ServiceUnavailable, ValidationFailed
from aegiswifi.database.engine import get_db
from aegiswifi.database.models import JobStatus
from aegiswifi.jobs import service as jobs_service
from aegiswifi.jobs.event_bus import JobEventEnvelope, get_event_bus
from aegiswifi.jobs.manager import get_job_manager
from aegiswifi.jobs.schemas import (
    JobCreate,
    JobEventLogRead,
    JobListRead,
    JobRead,
    JobStatusUpdate,
    JobUpdate,
)

router = APIRouter(prefix="/jobs", tags=["jobs"])
ws_router = APIRouter(tags=["jobs_ws"])


# ===================================================================
# REST endpoints
# ===================================================================


@router.get("", response_model=list[JobListRead])
def list_jobs(  # noqa: PLR0917 — FastAPI route params
    engagement_id: int | None = Query(None, ge=1),
    status: JobStatus | None = None,
    kind: str | None = Query(None, max_length=64),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> list[JobListRead]:
    return [
        JobListRead.model_validate(j)
        for j in jobs_service.list_jobs(
            db,
            engagement_id=engagement_id,
            status=status,
            kind=kind,
            limit=limit,
            offset=offset,
        )
    ]


@router.post("", response_model=JobRead, status_code=status.HTTP_201_CREATED)
def create_job(payload: JobCreate, db: Session = Depends(get_db)) -> JobRead:
    return JobRead.model_validate(jobs_service.create_job(db, payload))


@router.get("/{job_id}", response_model=JobRead)
def get_job(job_id: int, db: Session = Depends(get_db)) -> JobRead:
    return JobRead.model_validate(jobs_service.get_job(db, job_id))


@router.patch("/{job_id}", response_model=JobRead)
def update_job(
    job_id: int,
    payload: JobUpdate,
    db: Session = Depends(get_db),
) -> JobRead:
    return JobRead.model_validate(jobs_service.update_job(db, job_id, payload))


@router.post("/{job_id}/cancel", response_model=JobRead)
def cancel_job(
    job_id: int,
    payload: JobStatusUpdate | None = None,
    db: Session = Depends(get_db),
) -> JobRead:
    message = payload.message if payload else None
    job = jobs_service.cancel_job(db, job_id, message=message)
    # La cancelación asíncrona se procesa cuando el JobManager lo detecta.
    return JobRead.model_validate(job)


@router.post("/{job_id}/retry", response_model=JobRead)
def retry_job(job_id: int, db: Session = Depends(get_db)) -> JobRead:
    """Reintenta un trabajo fallido: lo transiciona de FAILED a CREATED."""
    job = jobs_service.get_job(db, job_id)
    current = JobStatus(job.status)
    if current != JobStatus.FAILED:
        raise ValidationFailed(f"trabajo {job_id} no está fallido (estado: {current.value})")
    # Limpiar campos de error y volver a CREATED.
    job = jobs_service.transition_job(  # noqa: E501
        db,
        job_id,
        JobStatus.CREATED,
        message="reintentado por operador",
    )
    return JobRead.model_validate(job)


@router.get("/{job_id}/events", response_model=list[JobEventLogRead])
def list_job_events(job_id: int, db: Session = Depends(get_db)) -> list[JobEventLogRead]:
    return [JobEventLogRead.model_validate(e) for e in jobs_service.list_job_events(db, job_id)]


@router.get("/queue/status")
def queue_status() -> dict[str, Any]:
    """Métricas actuales del gestor de cola (workers activos, cola pendiente)."""
    manager = get_job_manager()
    try:
        return manager.get_status()
    except RuntimeError as e:
        raise ServiceUnavailable("gestor de cola no disponible") from e


# ===================================================================
# WebSocket handler
# ===================================================================


@ws_router.websocket("/api/v1/ws/jobs")
async def job_events_ws(
    websocket: WebSocket,
    job_id: int | None = Query(None, ge=1),
    engagement_id: int | None = Query(None, ge=1),
) -> None:
    """WebSocket que emite eventos de trabajos en tiempo real.

    Parámetros opcionales:
      - job_id: filtrar por trabajo específico
      - engagement_id: filtrar por engagement

    Flujo:
      1. Acepta conexión.
      2. Envía replay de eventos recientes como array JSON.
      3. Escucha mensajes entrantes (para re-suscripción dinámica).
      4. Reenvía eventos del EventBus mientras la conexión esté abierta.
    """
    await websocket.accept()

    # Suscribir al bus de eventos.
    event_bus = get_event_bus()
    queue: asyncio.Queue[JobEventEnvelope] = asyncio.Queue(maxsize=500)
    try:
        event_bus.subscribe(queue, job_id=job_id or 0, engagement_id=engagement_id or 0)

        # Enviar replay de eventos recientes.
        replay = event_bus.get_replay(
            job_ids=[job_id] if job_id else None,
            engagement_ids=[engagement_id] if engagement_id else None,
            limit=100,
        )
        replay_data = [_envelope_to_dict(env) for env in replay]
        await websocket.send_json({"type": "replay", "events": replay_data})

        # Bucle principal: reenviar eventos del bus.
        while True:
            try:
                # Escuchar tanto mensajes del cliente como eventos del bus.
                envelope = await asyncio.wait_for(queue.get(), timeout=30.0)
                await websocket.send_json(
                    {
                        "type": "event",
                        "event": _envelope_to_dict(envelope),
                    }
                )
            except TimeoutError:
                # Enviar ping para mantener la conexión viva.
                try:
                    await websocket.send_json({"type": "ping"})
                except Exception:
                    break

    except WebSocketDisconnect:
        pass
    finally:
        event_bus.unsubscribe(queue)


def _envelope_to_dict(env: JobEventEnvelope) -> dict[str, object]:
    return {
        "event_type": env.event_type,
        "job_id": env.job_id,
        "engagement_id": env.engagement_id,
        "data": env.data,
        "timestamp": env.timestamp,
    }
