"""Importación de alcance a un engagement (minuta §12, CLI §33 ``scope import``).

Convierte un :class:`ScopeFile` parseado en registros ``ScopeTarget`` y guarda
permisos/límites en el engagement. La var. de autorización se registra en
``authorization_reference``.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from aegiswifi.core.exceptions import ValidationFailed
from aegiswifi.database.models import Engagement, ScopeTarget
from aegiswifi.engagements.service import get_engagement
from aegiswifi.scope.parser import parse_scope_file
from aegiswifi.scope.schemas import ScopeFile


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
