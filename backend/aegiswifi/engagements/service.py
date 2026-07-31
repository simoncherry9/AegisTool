"""Lógica de dominio de engagements (minuta §11 reglas).

Reglas de §11 reflejadas aquí:
  * Solo un engagement activo por interfaz  → (se aplica en Fase 3 con interfaces).
  * Un trabajo no puede iniciarse sin engagement → (job system, Fase 1 completa).
  * Un engagement vencido no puede ejecutar trabajos → ``is_expired``.
  * El cierre detiene trabajos y restaura interfaces → ``close`` (stubs por ahora).
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from aegiswifi.core.exceptions import Conflict, NotFound, ScopeViolation, ValidationFailed
from aegiswifi.database.models import Engagement, EngagementStatus
from aegiswifi.engagements.schemas import EngagementCreate, EngagementUpdate


def generate_code(session: Session, *, year: int | None = None) -> str:
    """Genera el siguiente código de engagement formateado ``ENG-YYYY-NNN``."""
    year = year or datetime.now(UTC).year
    prefix = f"ENG-{year}-"
    stmt = select(Engagement.code).where(Engagement.code.like(f"{prefix}%"))
    existing = session.scalars(stmt).all()
    next_n = 1
    for code in existing:
        try:
            next_n = max(next_n, int(code.rsplit("-", 1)[-1]) + 1)
        except ValueError:
            continue
    return f"{prefix}{next_n:03d}"


def create_engagement(session: Session, payload: EngagementCreate) -> Engagement:
    operator_name = payload.operator
    if payload.operator_id:
        from aegiswifi.database.models import User
        user = session.get(User, payload.operator_id)
        if user:
            operator_name = user.full_name or user.username

    engagement = Engagement(
        code=generate_code(session),
        name=payload.name,
        client=payload.client,
        operator=operator_name,
        operator_id=payload.operator_id,
        status=EngagementStatus.DRAFT,
        start_date=payload.start_date,
        end_date=payload.end_date,
        authorization_reference=payload.authorization_reference,
        permissions=payload.permissions,
        limits=payload.limits,
        notes=payload.notes,
    )
    session.add(engagement)
    session.commit()
    session.refresh(engagement)
    return engagement


def list_engagements(session: Session) -> list[Engagement]:
    return list(session.scalars(select(Engagement).order_by(Engagement.id.desc())))


def get_engagement(session: Session, engagement_id: int) -> Engagement:
    engagement = session.get(Engagement, engagement_id)
    if engagement is None:
        raise NotFound(f"engagement {engagement_id} no encontrado")
    return engagement


def update_engagement(
    session: Session, engagement_id: int, payload: EngagementUpdate
) -> Engagement:
    engagement = get_engagement(session, engagement_id)
    data = payload.model_dump(exclude_unset=True)
    if "status" in data and isinstance(data["status"], EngagementStatus):
        data["status"] = data["status"].value
    for key, value in data.items():
        setattr(engagement, key, value)
    session.commit()
    session.refresh(engagement)
    return engagement


def activate(session: Session, engagement_id: int) -> Engagement:
    """Pasa de DRAFT/PAUSED → ACTIVE. Regla §11: un engagement activo por interfaz
    se aplica cuando exista el módulo de interfaces."""
    engagement = get_engagement(session, engagement_id)
    if engagement.status in {EngagementStatus.COMPLETED, EngagementStatus.CANCELLED}:
        raise Conflict(f"engagement {engagement.code} está {engagement.status}")
    if engagement.status == EngagementStatus.ACTIVE:
        return engagement
    engagement.status = EngagementStatus.ACTIVE
    session.commit()
    session.refresh(engagement)
    return engagement


def close(session: Session, engagement_id: int) -> Engagement:
    """Cierra un engagement: restaura interfaces y detiene trabajos (minuta §11).

    En esta fase solo cambia el estado; el JobManager y la restauración de
    interfaces se conectan cuando existan esos módulos.
    """
    engagement = get_engagement(session, engagement_id)
    if engagement.status == EngagementStatus.ARCHIVED:
        raise Conflict(f"engagement {engagement.code} ya está archivado")
    engagement.status = EngagementStatus.COMPLETED
    session.commit()
    session.refresh(engagement)
    return engagement


def is_expired(engagement: Engagement, now: datetime | None = None) -> bool:
    """§11: un engagement vencido no puede ejecutar trabajos."""
    if engagement.end_date is None:
        return False
    now = now or datetime.now(UTC)
    return engagement.end_date < now


def assert_active_and_not_expired(engagement: Engagement) -> None:
    """Preámbulo común para cualquier acción que requiera engagement válido."""
    if engagement.status != EngagementStatus.ACTIVE:
        raise ValidationFailed(
            f"engagement {engagement.code} no está activo (estado: {engagement.status})"
        )
    if is_expired(engagement):
        raise ScopeViolation(f"engagement {engagement.code} está vencido")
