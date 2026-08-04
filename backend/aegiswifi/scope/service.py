"""Importación de alcance a un engagement (minuta §12, CLI §33 ``scope import``).

Convierte un :class:`ScopeFile` parseado en registros ``ScopeTarget`` y guarda
permisos/límites en el engagement. La var. de autorización se registra en
``authorization_reference``.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from aegiswifi.core.exceptions import ValidationFailed
from aegiswifi.database.models import Engagement, ScopeTarget
from aegiswifi.engagements.service import get_engagement
from aegiswifi.scope.parser import parse_scope_file
from aegiswifi.scope.schemas import ScopeFile
from aegiswifi.scope.policy import PolicyEngine, ScopeContext
from aegiswifi.scope.schemas import Limits, Permissions, ScopeBlock


def import_scope(
    session: Session, engagement_id: int, path: str | Path
) -> tuple[Engagement, ScopeFile]:
    """Importa un archivo de alcance a un engagement existente.

    Reemplaza los ``ScopeTarget`` previos del engagement (alcance es autoritativo).
    """
    scope_file = parse_scope_file(path)
    engagement = get_engagement(session, engagement_id)

    # Cruza la cabecera del archivo con el engagement.
    if scope_file.engagement.id != engagement.code:
        raise ValidationFailed(
            f"el id del archivo ({scope_file.engagement.id}) no coincide con el "
            f"engagement ({engagement.code})"
        )
    engagement.permissions = scope_file.permissions.model_dump()
    engagement.limits = scope_file.limits.model_dump()
    engagement.authorization_reference = str(path)
    engagement.start_date = scope_file.engagement.valid_from
    engagement.end_date = scope_file.engagement.valid_until

    # Reemplaza objetivos.
    session.query(ScopeTarget).where(ScopeTarget.engagement_id == engagement_id).delete()
    for ssid in scope_file.scope.allowed_ssids:
        session.add(ScopeTarget(engagement_id=engagement_id, ssid=ssid))
    for bssid in scope_file.scope.allowed_bssids:
        session.add(ScopeTarget(engagement_id=engagement_id, bssid=bssid))
    for client in scope_file.scope.allowed_clients:
        session.add(
            ScopeTarget(
                engagement_id=engagement_id,
                bssid=client,  # TODO: columna dedicada a clientes (Fase 3)
                permission_level="client",
            )
        )
    session.commit()
    session.refresh(engagement)
    return engagement, scope_file


def build_policy_engine(session: Session, engagement_id: int) -> PolicyEngine:
    """Construye el guardián de alcance desde el engagement persistido.

    Esta es la entrada compartida por captura y cracking para que ninguna
    acción activa dependa de validaciones dispersas en handlers HTTP.
    """
    from aegiswifi.engagements.service import assert_active_and_not_expired

    engagement = get_engagement(session, engagement_id)
    assert_active_and_not_expired(engagement)
    targets = list(
        session.scalars(
            select(ScopeTarget).where(ScopeTarget.engagement_id == engagement_id)
        ).all()
    )
    now = datetime.now(UTC)

    def _aware(value: datetime | None, fallback: datetime) -> datetime:
        if value is None:
            return fallback
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value

    scope = ScopeBlock(
        allowed_ssids=sorted({target.ssid for target in targets if target.ssid}),
        allowed_bssids=sorted(
            {
                target.bssid
                for target in targets
                if target.bssid and target.permission_level != "client"
            }
        ),
        allowed_clients=sorted(
            {
                target.bssid
                for target in targets
                if target.bssid and target.permission_level == "client"
            }
        ),
        channels=sorted({target.channel for target in targets if target.channel is not None}),
        bands=sorted({target.band for target in targets if target.band}),
    )
    context = ScopeContext(
        engagement_code=engagement.code,
        valid_from=_aware(engagement.start_date, now - timedelta(days=36500)),
        valid_until=_aware(engagement.end_date, now + timedelta(days=36500)),
        scope=scope,
        permissions=Permissions.model_validate(engagement.permissions),
        limits=Limits.model_validate(engagement.limits),
        operator=engagement.operator,
    )
    return PolicyEngine(context)
