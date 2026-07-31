"""Lógica de dominio del sistema de trabajos (minuta §26).

Funciones que reciben ``session: Session`` como primer argumento, siguiendo el patrón
de :mod:`aegiswifi.engagements.service`:
  * Crean/consultan tuplas en la BD.
  * Validan transiciones de estado vía :class:`JobStateMachine`.
  * Validan el engagement vía :func:`aegiswifi.engagements.service.assert_active_and_not_expired`.
  * Hacen ``commit`` y ``refresh`` antes de retornar.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from aegiswifi.core.exceptions import NotFound, ValidationFailed
from aegiswifi.database.models import Job, JobEventLog, JobStatus
from aegiswifi.engagements import service as engagements_service
from aegiswifi.jobs.schemas import JobCreate, JobUpdate
from aegiswifi.jobs.statemachine import JobStateMachine
from aegiswifi.scope.policy import PolicyEngine, ScopeContext


def create_job(session: Session, payload: JobCreate) -> Job:
    """Crea un trabajo en estado CREATED, validando que el engagement exista."""
    engagement = engagements_service.get_engagement(session, payload.engagement_id)

    job = Job(
        engagement_id=engagement.id,
        kind=payload.kind,
        status=JobStatus.CREATED,
        priority=payload.priority,
        timeout_seconds=payload.timeout_seconds,
        parameters=payload.parameters,
    )
    session.add(job)
    session.flush()

    # Log inicial del evento de creación.
    event = JobEventLog(job_id=job.id, from_status=None, to_status=JobStatus.CREATED.value)
    session.add(event)
    session.commit()
    session.refresh(job)
    return job


def get_job(session: Session, job_id: int) -> Job:
    """Retorna un trabajo por ID o lanza :class:`NotFound`."""
    job = session.get(Job, job_id)
    if job is None:
        raise NotFound(f"trabajo {job_id} no encontrado")
    return job


def list_jobs(
    session: Session,
    *,
    engagement_id: int | None = None,
    status: JobStatus | None = None,
    kind: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[Job]:
    """Lista trabajos con filtros opcionales, ordenados por priority DESC, created_at DESC."""
    stmt = select(Job).order_by(Job.priority.desc(), Job.created_at.desc())
    if engagement_id is not None:
        stmt = stmt.where(Job.engagement_id == engagement_id)
    if status is not None:
        stmt = stmt.where(Job.status == status.value)
    if kind is not None:
        stmt = stmt.where(Job.kind == kind)
    stmt = stmt.limit(limit).offset(offset)
    return list(session.scalars(stmt).all())


def update_job(session: Session, job_id: int, payload: JobUpdate) -> Job:
    """Actualiza campos de un trabajo, validando transiciones de estado."""
    job = get_job(session, job_id)
    data = payload.model_dump(exclude_unset=True)

    # Si se cambia el estado, validar la transición.
    new_status_val = data.get("status")
    if new_status_val is not None:
        current_status = JobStatus(job.status)
        new_status = (
            new_status_val if isinstance(new_status_val, JobStatus) else JobStatus(new_status_val)
        )
        JobStateMachine.assert_valid_transition(current_status, new_status)
        data["status"] = new_status.value

        # Log de transición.
        event = JobEventLog(
            job_id=job.id,
            from_status=current_status.value,
            to_status=new_status.value,
            message=data.get("error_message"),
        )
        session.add(event)

        # Si es terminal, registrar finished_at.
        if JobStateMachine.is_terminal(new_status):
            data["finished_at"] = datetime.now(UTC)

    for key, value in data.items():
        setattr(job, key, value)

    session.commit()
    session.refresh(job)
    return job


def transition_job(
    session: Session, job_id: int, new_status: JobStatus, message: str | None = None
) -> Job:
    """Transiciona un trabajo al estado indicado. Atajo para el caso común."""
    return update_job(session, job_id, JobUpdate(status=new_status, error_message=message))


def cancel_job(session: Session, job_id: int, message: str | None = None) -> Job:
    """Transiciona un trabajo a CANCELLING (si no está ya en terminal)."""
    job = get_job(session, job_id)
    current = JobStatus(job.status)
    if JobStateMachine.is_terminal(current):
        raise ValidationFailed(f"trabajo {job_id} ya está en estado terminal: {current.value}")
    return transition_job(session, job_id, JobStatus.CANCELLING, message=message)


def list_job_events(session: Session, job_id: int) -> list[JobEventLog]:
    """Retorna el historial de eventos de un trabajo."""
    get_job(session, job_id)  # valida existencia
    stmt = (
        select(JobEventLog)
        .where(JobEventLog.job_id == job_id)
        .order_by(JobEventLog.created_at.asc())
    )
    return list(session.scalars(stmt).all())


def claim_next_queued(session: Session) -> Job | None:
    """Reclama transaccionalmente el trabajo QUEUED de mayor prioridad (FIFO dentro de prioridad).

    Retorna ``None`` si no hay trabajos en cola.
    """
    stmt = (
        select(Job)
        .where(Job.status == JobStatus.QUEUED.value)
        .order_by(Job.priority.desc(), Job.created_at.asc())
        .limit(1)
    )
    job = session.scalars(stmt).first()
    if job is None:
        return None
    # Marcar como PREPARING (siguiente paso lógico después de QUEUED).
    event = JobEventLog(
        job_id=job.id,
        from_status=job.status,
        to_status=JobStatus.PREPARING.value,
        message="reclamado por el gestor de trabajos",
    )
    job.status = JobStatus.PREPARING.value
    session.add(event)
    session.commit()
    session.refresh(job)
    return job


def mark_stale_jobs(session: Session, heartbeat_timeout_seconds: int = 30) -> list[Job]:
    """Encuentra trabajos RUNNING sin heartbeat reciente y los transiciona a FAILED."""
    cutoff = datetime.now(UTC)
    stmt = (
        select(Job)
        .where(Job.status == JobStatus.RUNNING.value)
        .where((Job.heartbeat_at.is_(None)) | (Job.heartbeat_at < cutoff))
    )
    stale: list[Job] = []
    for job in session.scalars(stmt).all():
        if job.heartbeat_at is not None:
            delta = (cutoff - job.heartbeat_at).total_seconds()
            if delta < heartbeat_timeout_seconds:
                continue
        event = JobEventLog(
            job_id=job.id,
            from_status=job.status,
            to_status=JobStatus.FAILED.value,
            message="heartbeat vencido — trabajo marcado como fallido",
        )
        job.status = JobStatus.FAILED.value
        job.finished_at = cutoff
        job.error_message = "heartbeat vencido"
        session.add(event)
        stale.append(job)
    if stale:
        session.commit()
        for j in stale:
            session.refresh(j)
    return stale


def validate_job_scope(job: Job, scope_context: ScopeContext) -> None:
    """Valida que el trabajo esté dentro del alcance autorizado usando el PolicyEngine.

    Lanza :class:`ScopeViolation` si la acción no está permitida.
    """
    engine = PolicyEngine(scope_context)
    if job.kind == "passive_capture":
        engine.assert_allowed("passive_capture")
    elif job.kind == "handshake_capture":
        engine.assert_allowed("handshake_capture")
    elif job.kind == "pmkid_capture":
        engine.assert_allowed("pmkid_capture")
    elif job.kind == "controlled_reconnect":
        engine.assert_allowed("controlled_reconnect")
    elif job.kind == "password_audit":
        engine.assert_allowed("password_audit")
    elif job.kind == "wps_testing":
        engine.assert_allowed("wps_testing")
    elif job.kind == "enterprise_testing":
        engine.assert_allowed("enterprise_testing")
    elif job.kind == "denial_of_service":
        engine.assert_allowed("denial_of_service")
    elif job.kind == "protocol_fuzzing":
        engine.assert_allowed("protocol_fuzzing")
    # isolation_test y rogue_ap_detection no tienen permiso directo en PolicyEngine aún,
    # se validarán cuando se implementen esos módulos.
