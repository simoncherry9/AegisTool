"""REST API del motor de hallazgos (minuta §29, §28).

Endpoints:
  GET    /findings              — listar hallazgos
  POST   /findings              — crear hallazgo manual
  GET    /findings/summary      — resumen de hallazgos
  GET    /findings/rules        — listar reglas registradas
  GET    /findings/{id}         — detalle de un hallazgo
  PATCH  /findings/{id}         — actualizar un hallazgo
  DELETE /findings/{id}         — eliminar un hallazgo
  POST   /findings/engine/run   — ejecutar motor de hallazgos
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from aegiswifi.database.engine import get_db
from aegiswifi.database.models import Engagement
from aegiswifi.findings.engine import get_findings_engine
from aegiswifi.findings.schemas import (
    EngineResult,
    FindingCreate,
    FindingRead,
    FindingRule,
    FindingSummary,
    FindingUpdate,
)

router = APIRouter(prefix="/findings", tags=["findings"])


# ===================================================================
# Rules
# ===================================================================


@router.get("/rules", response_model=list[FindingRule])
def list_rules() -> list[FindingRule]:
    """Lista las reglas de detección registradas."""
    engine = get_findings_engine()
    return engine.rules


# ===================================================================
# List / Create
# ===================================================================


@router.get("", response_model=list[FindingRead])
def list_findings(
    engagement_id: int | None = Query(None, ge=1),
    severity: str | None = Query(None, max_length=16),
    category: str | None = Query(None, max_length=64),
    status: str | None = Query(None, max_length=32),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),  # noqa: B008
) -> list[FindingRead]:
    """Lista hallazgos con filtros opcionales."""
    engine = get_findings_engine()
    return engine.list_findings(
        db,
        engagement_id=engagement_id,
        severity=severity,
        category=category,
        status=status,
        limit=limit,
    )


@router.post("", response_model=FindingRead, status_code=status.HTTP_201_CREATED)
def create_finding(
    data: FindingCreate,
    db: Session = Depends(get_db),  # noqa: B008
) -> FindingRead:
    """Crea un hallazgo manualmente."""
    # Verificar que el engagement existe.
    engagement = db.get(Engagement, data.engagement_id)
    if engagement is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Engagement #{data.engagement_id} no encontrado",
        )

    engine = get_findings_engine()
    return engine.create_finding(db, data)


# ===================================================================
# Summary
# ===================================================================


@router.get("/summary", response_model=FindingSummary)
def get_findings_summary(
    engagement_id: int = Query(..., ge=1),
    db: Session = Depends(get_db),  # noqa: B008
) -> FindingSummary:
    """Resumen de hallazgos para un engagement."""
    # Verificar que el engagement existe.
    engagement = db.get(Engagement, engagement_id)
    if engagement is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Engagement #{engagement_id} no encontrado",
        )

    engine = get_findings_engine()
    return engine.get_summary(db, engagement_id)


# ===================================================================
# Get / Update / Delete
# ===================================================================


@router.get("/{finding_id}", response_model=FindingRead)
def get_finding(
    finding_id: int,
    db: Session = Depends(get_db),  # noqa: B008
) -> FindingRead:
    """Obtiene el detalle de un hallazgo."""
    engine = get_findings_engine()
    finding = engine.get_finding(db, finding_id)
    if finding is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Finding #{finding_id} no encontrado",
        )
    return finding


@router.patch("/{finding_id}", response_model=FindingRead)
def update_finding(
    finding_id: int,
    data: FindingUpdate,
    db: Session = Depends(get_db),  # noqa: B008
) -> FindingRead:
    """Actualiza un hallazgo existente."""
    engine = get_findings_engine()
    update_data = data.model_dump(exclude_none=True)
    finding = engine.update_finding(db, finding_id, update_data)
    if finding is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Finding #{finding_id} no encontrado",
        )
    return finding


@router.delete("/{finding_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_finding(
    finding_id: int,
    db: Session = Depends(get_db),  # noqa: B008
) -> None:
    """Elimina un hallazgo."""
    engine = get_findings_engine()
    if not engine.delete_finding(db, finding_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Finding #{finding_id} no encontrado",
        )


# ===================================================================
# Engine execution
# ===================================================================


@router.post("/engine/run", response_model=EngineResult)
def run_findings_engine(
    engagement_id: int | None = Query(None, ge=1),
    context_json: str | None = Query(None, max_length=10000),
    db: Session = Depends(get_db),  # noqa: B008
) -> EngineResult:
    """Ejecuta el motor de hallazgos.

    Opcionalmente puede limitarse a un engagement específico y recibir
    contexto adicional (WPS, PMF, etc.) como JSON.
    """
    import json

    engine = get_findings_engine()
    context: dict[str, object] = {}
    if context_json:
        try:
            context = json.loads(context_json)
        except json.JSONDecodeError as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"context_json inválido: {e}",
            ) from e

    if engagement_id:
        engagement = db.get(Engagement, engagement_id)
        if engagement is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Engagement #{engagement_id} no encontrado",
            )
        return engine.run_for_engagement(engagement, db, context)

    return engine.run_all(db, context)
