"""Lógica de dominio del módulo de evidencia (minuta §30).

Funciones sync que reciben ``session: Session`` como primer argumento,
siguiendo el mismo patrón que :mod:`aegiswifi.jobs.service`.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from aegiswifi.core.exceptions import NotFound
from aegiswifi.database.models import Capture


def get_evidence(session: Session, evidence_id: int) -> Capture:
    """Retorna una captura por ID o lanza :class:`NotFound`."""
    capture = session.get(Capture, evidence_id)
    if capture is None:
        raise NotFound(f"evidencia {evidence_id} no encontrada")
    return capture


def list_evidence(
    session: Session,
    *,
    engagement_id: int | None = None,
    job_id: int | None = None,
    category: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[Capture]:
    """Lista capturas con filtros opcionales, ordenadas por created_at DESC."""
    stmt = select(Capture).order_by(Capture.created_at.desc())
    if engagement_id is not None:
        stmt = stmt.where(Capture.engagement_id == engagement_id)
    if job_id is not None:
        stmt = stmt.where(Capture.job_id == job_id)
    if category is not None:
        stmt = stmt.where(Capture.category == category)
    stmt = stmt.limit(limit).offset(offset)
    return list(session.scalars(stmt).all())
