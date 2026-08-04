"""REST API del módulo de validación de handshakes (minuta §15, §16, §28).

Endpoints:
  POST   /validation/validate        — validar una captura
  GET    /validation/artifacts       — listar artifacts validados
  GET    /validation/artifacts/{id}  — detalle de un artifact
  POST   /validation/reprocess/{id}  — reprocesar un artifact
  GET    /validation/artifacts/{id}/report — reporte legible
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from aegiswifi.database.engine import get_db
from aegiswifi.database.models import (
    Capture,
    Engagement,
    EngagementStatus,
    HandshakeArtifact,
)
from aegiswifi.validation.schemas import (
    HandshakeReport,
    ValidationRequest,
    ValidationResult,
)
from aegiswifi.validation.service import get_validation_service

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
        source_path = Path(req.file_path).expanduser().resolve()
        if not source_path.is_file():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Archivo de captura no encontrado: {source_path}",
            )
        capture_format = source_path.suffix.lower().lstrip(".")
        if capture_format not in {"cap", "pcap", "pcapng"}:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Formato no soportado; utiliza .cap, .pcap o .pcapng",
            )

        eng_id = req.engagement_id
        if eng_id:
            engagement = db.get(Engagement, eng_id)
            if engagement is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Engagement #{eng_id} no encontrado",
                )
        else:
            active_eng = (
                db.query(Engagement).filter_by(status=EngagementStatus.ACTIVE.value).first()
            )
            if active_eng is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Selecciona un engagement antes de validar la captura",
                )
            eng_id = active_eng.id

        sha256 = hashlib.sha256()
        with source_path.open("rb") as source:
            for chunk in iter(lambda: source.read(65536), b""):
                sha256.update(chunk)

        capture = Capture(
            engagement_id=eng_id,
            path=str(source_path),
            category="handshake",
            format=capture_format,
            sha256=sha256.hexdigest(),
            original_filename=source_path.name,
            size_bytes=source_path.stat().st_size,
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
) -> list[dict[str, object]]:
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
) -> dict[str, object]:
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
