"""REST API del módulo de evidencia (minuta §30).

Endpoints:
  GET    /evidence         — listar evidencia con filtros
  GET    /evidence/{id}    — detalle de una evidencia
  GET    /evidence/{id}/download — descargar archivo
  DELETE /evidence/{id}    — eliminar registro de evidencia
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from aegiswifi.core.exceptions import NotFound
from aegiswifi.database.engine import get_db
from aegiswifi.evidence import service as evidence_service
from aegiswifi.evidence.schemas import CaptureListRead, CaptureRead

router = APIRouter(prefix="/evidence", tags=["evidence"])


@router.get("", response_model=list[CaptureListRead])
def list_evidence(  # noqa: PLR0917 — FastAPI route params
    engagement_id: int | None = Query(None, ge=1),
    job_id: int | None = Query(None, ge=1),
    category: str | None = Query(None, max_length=32),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),  # noqa: B008
) -> list[CaptureListRead]:
    return [
        CaptureListRead.model_validate(c)
        for c in evidence_service.list_evidence(
            db,
            engagement_id=engagement_id,
            job_id=job_id,
            category=category,
            limit=limit,
            offset=offset,
        )
    ]


@router.get("/{evidence_id}", response_model=CaptureRead)
def get_evidence(evidence_id: int, db: Session = Depends(get_db)) -> CaptureRead:  # noqa: B008
    return CaptureRead.model_validate(evidence_service.get_evidence(db, evidence_id))


@router.get("/{evidence_id}/download")
def download_evidence(evidence_id: int, db: Session = Depends(get_db)) -> FileResponse:  # noqa: B008
    """Descarga el archivo de evidencia."""
    capture = evidence_service.get_evidence(db, evidence_id)
    path = Path(capture.path)
    if not path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="archivo de evidencia no encontrado en disco",
        )
    return FileResponse(
        path,
        media_type="application/octet-stream",
        filename=path.name,
    )


@router.delete("/{evidence_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_evidence(evidence_id: int, db: Session = Depends(get_db)) -> None:  # noqa: B008
    """Elimina el registro de evidencia (no el archivo en disco)."""
    try:
        evidence_service.delete_evidence(db, evidence_id)
    except NotFound as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
