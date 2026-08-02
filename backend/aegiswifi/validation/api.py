"""REST API del módulo de validación de handshakes (minuta §15, §16, §28).

Endpoints:
  POST   /validation/validate        — validar una captura
  GET    /validation/artifacts       — listar artifacts validados
  GET    /validation/artifacts/{id}  — detalle de un artifact
  POST   /validation/reprocess/{id}  — reprocesar un artifact
  GET    /validation/artifacts/{id}/report — reporte legible
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from aegiswifi.database.engine import get_db
from aegiswifi.database.models import Capture, HandshakeArtifact
from aegiswifi.validation.schemas import (
    HandshakeReport,
    QualityClassification,
    ValidationRequest,
    ValidationResult,
)
from aegiswifi.validation.service import HandshakeValidationService, get_validation_service

router = APIRouter(prefix="/validation", tags=["validation"])


# ===================================================================
# Schemas de request/response de la API
# ===================================================================


class ValidateResponse(BaseModel):
    """Respuesta de ``POST /validation/validate``."""

    result: ValidationResult


# ===================================================================
# Validate
# ===================================================================


@router.post("/validate", response_model=ValidateResponse)
async def validate_capture(
    req: ValidationRequest,
    db: Session = Depends(get_db),  # noqa: B008
) -> ValidateResponse:
    """Valida una captura — analiza handshakes EAPOL/PMKID y clasifica calidad.

    Recibe un ``capture_id`` o un ``file_path`` directo. Si se provee
    ``engagement_id``, el artifact se asocia al engagement.
    """
    service = get_validation_service()
    capture: Capture | None = None

    if req.capture_id:
        capture = db.get(Capture, req.capture_id)
        if capture is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Capture #{req.capture_id} no encontrado",
            )

    if not req.capture_id and not req.file_path:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Se requiere capture_id o file_path",
        )

    if not capture and req.file_path:
        # Si se envía solo el file_path manual, debemos crear un Capture 
        # en la base de datos para poder persistir el Artifact.
        from aegiswifi.database.models import Engagement, EngagementStatus
        eng_id = req.engagement_id
        if not eng_id:
            active_eng = db.query(Engagement).filter_by(status=EngagementStatus.ACTIVE.value).first()
            eng_id = active_eng.id if active_eng else 1
            
        capture = Capture(
            engagement_id=eng_id,
            path=req.file_path,
            category="handshake",
            format="pcapng"
        )
        db.add(capture)
        db.commit()
        db.refresh(capture)

    result = await service.validate_capture(
        capture=capture,
        file_path=req.file_path,
        db_session=db,
        force=req.force_reprocess,
    )

    if result.errors and not result.validated:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": "La validación falló",
                "errors": result.errors,
                "quality": result.quality.value,
                "score": result.quality_score,
            },
        )

    return ValidateResponse(result=result)


# ===================================================================
# Artifacts CRUD
# ===================================================================


@router.get("/artifacts", response_model=list[HandshakeReport])
def list_artifacts(
    capture_id: int | None = Query(None, ge=1),
    validated: bool | None = Query(None),
    quality: str | None = Query(None, max_length=16),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),  # noqa: B008
) -> list[dict]:
    """Lista HandshakeArtifacts, opcionalmente filtrados."""
    from sqlalchemy import select

    stmt = select(HandshakeArtifact)
    if capture_id is not None:
        stmt = stmt.where(HandshakeArtifact.capture_id == capture_id)
    if validated is not None:
        stmt = stmt.where(HandshakeArtifact.validated == validated)
    if quality:
        stmt = stmt.where(HandshakeArtifact.quality == quality)

    stmt = stmt.order_by(HandshakeArtifact.id.desc()).limit(limit)
    artifacts = list(db.scalars(stmt).all())

    service = get_validation_service()
    return [service.build_report(a) for a in artifacts]


@router.get("/artifacts/{artifact_id}", response_model=HandshakeReport)
def get_artifact(
    artifact_id: int,
    db: Session = Depends(get_db),  # noqa: B008
) -> dict:
    """Obtiene el detalle de un HandshakeArtifact."""
    artifact = db.get(HandshakeArtifact, artifact_id)
    if artifact is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"HandshakeArtifact #{artifact_id} no encontrado",
        )

    service = get_validation_service()
    return service.build_report(artifact)


@router.post("/reprocess/{artifact_id}", response_model=ValidateResponse)
async def reprocess_artifact(
    artifact_id: int,
    db: Session = Depends(get_db),  # noqa: B008
) -> ValidateResponse:
    """Reprocesa un HandshakeArtifact existente (reescanea con hcxpcapngtool)."""
    artifact = db.get(HandshakeArtifact, artifact_id)
    if artifact is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"HandshakeArtifact #{artifact_id} no encontrado",
        )

    capture = db.get(Capture, artifact.capture_id) if artifact.capture_id else None

    service = get_validation_service()
    result = await service.validate_capture(
        capture=capture,
        db_session=db,
        force=True,
    )

    return ValidateResponse(result=result)
