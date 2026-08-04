"""REST API del módulo de cracking (minuta §18, §28).

Endpoints:
  GET    /cracking/dictionaries          — listar wordlists disponibles
  GET    /cracking/rules                 — listar reglas disponibles
  POST   /cracking/analyze/{artifact_id} — analizar handshake y generar plan
  GET    /cracking/jobs                  — listar CrackingJobs
  POST   /cracking/jobs                  — crear un CrackingJob
  GET    /cracking/jobs/{job_id}         — detalle de un CrackingJob
  POST   /cracking/jobs/{job_id}/start   — ejecutar plan de cracking
  GET    /cracking/jobs/{job_id}/progress — progreso en vivo
  POST   /cracking/jobs/{job_id}/cancel  — cancelar un CrackingJob
  GET    /cracking/handshakes/{artifact_id}/hashinfo — info del hash .22000
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from aegiswifi.cracking.dictionary import DictionaryManager
from aegiswifi.cracking.planner import CrackingPlanner
from aegiswifi.cracking.rules import RulesManager
from aegiswifi.cracking.schemas import (
    AttackMode,
    CrackingJobRead,
    CrackingPlan,
    DictionaryInfo,
    HashInfo,
    RuleInfo,
)
from aegiswifi.cracking.service import get_cracking_service
from aegiswifi.database.engine import get_db
from aegiswifi.database.models import CrackingJob, HandshakeArtifact

router = APIRouter(prefix="/cracking", tags=["cracking"])

# Helpers reutilizables (singletons ligeros).
_dict_manager = DictionaryManager()
_rules_manager = RulesManager()
_planner = CrackingPlanner(_dict_manager, _rules_manager)


def _validate_preferred_paths(paths: list[str] | None, kind: str) -> list[str]:
    """Devuelve warnings para paths preferidos inexistentes o inválidos.

    Se permite cualquier ruta que exista en disco; si no existe o es un
    directorio, se informa al usuario para que la corrija.
    """
    if not paths:
        return []

    warnings: list[str] = []
    for path in paths:
        candidate = Path(path)
        if not candidate.exists():
            warnings.append(f"El {kind} no existe: {path}")
        elif not candidate.is_file():
            warnings.append(f"El {kind} no es un archivo válido: {path}")
    return warnings


# ===================================================================
# Schemas de request/response de la API
# ===================================================================


class AnalyzeResponse(BaseModel):
    """Respuesta de ``POST /analyze/{artifact_id}``."""

    plan: CrackingPlan
    hash_info: HashInfo | None = None
    warnings: list[str] = []


class StartJobResponse(BaseModel):
    """Respuesta de ``POST /jobs/{job_id}/start``."""

    job_id: int
    status: str


# ===================================================================
# Dictionaries & Rules
# ===================================================================


class CustomWordlistCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    words: list[str] = Field(min_length=1, max_length=1_000_000)


class DictionaryDecompressRequest(BaseModel):
    path: str = Field(min_length=1, max_length=1024)


@router.get("/dictionaries", response_model=list[DictionaryInfo])
def list_dictionaries(
    force_rescan: bool = Query(False),
) -> list[DictionaryInfo]:
    """Lista las wordlists disponibles en el sistema."""
    return _dict_manager.scan_all(force=force_rescan)


@router.post(
    "/dictionaries/custom", response_model=DictionaryInfo, status_code=status.HTTP_201_CREATED
)
def create_custom_dictionary(body: CustomWordlistCreate) -> DictionaryInfo:
    """Crea un diccionario de palabras personalizado."""
    if not body.words:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La lista de palabras no puede estar vacía",
        )
    try:
        return _dict_manager.create_custom_wordlist(body.name, body.words)
    except (ValueError, FileExistsError) as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post("/dictionaries/decompress", response_model=DictionaryInfo)
def decompress_dictionary(body: DictionaryDecompressRequest) -> DictionaryInfo:
    """Descomprime de forma segura una wordlist ya detectada en el sistema."""
    try:
        return _dict_manager.decompress_wordlist(body.path)
    except FileExistsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except (ValueError, OSError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.delete("/dictionaries/custom/{name}", status_code=status.HTTP_204_NO_CONTENT)
def delete_custom_dictionary(name: str) -> None:
    """Elimina un diccionario personalizado."""
    deleted = _dict_manager.delete_custom_wordlist(name)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Diccionario '{name}' no encontrado"
        )


@router.get("/rules", response_model=list[RuleInfo])
def list_rules(
    force_rescan: bool = Query(False),
) -> list[RuleInfo]:
    """Lista los archivos de reglas disponibles en el sistema."""
    return _rules_manager.scan_all(force=force_rescan)


# ===================================================================
# Analyze handshake
# ===================================================================


@router.post("/analyze/{artifact_id}", response_model=AnalyzeResponse)
def analyze_handshake(
    artifact_id: int,
    preferred_dicts: list[str] | None = Query(None),
    preferred_rules: list[str] | None = Query(None),
    skip_modes: list[AttackMode] | None = Query(None),
    max_total_time: int = Query(3600, ge=60, le=86400),
    db: Session = Depends(get_db),  # noqa: B008
) -> AnalyzeResponse:
    """Analiza un handshake y genera un plan de cracking."""
    artifact = db.get(HandshakeArtifact, artifact_id)
    if artifact is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"HandshakeArtifact #{artifact_id} no encontrado",
        )

    warnings: list[str] = []
    hash_info: HashInfo | None = None
    service = get_cracking_service()

    try:
        service.validate_artifact(artifact)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e

    hash_info = service.get_hash_info(artifact)

    warnings.extend(_validate_preferred_paths(preferred_dicts, "diccionario"))
    warnings.extend(_validate_preferred_paths(preferred_rules, "regla"))

    capture = artifact.capture
    plan = _planner.build_plan(
        job_id=0,  # se asigna al crear el job
        artifact_id=artifact_id,
        hash_file_path=artifact.hash22000_path or "",
        max_total_time=max_total_time,
        preferred_dicts=preferred_dicts,
        preferred_rules=preferred_rules,
        skip_modes=skip_modes,
        cap_file_path=capture.path if capture else None,
        bssid=capture.bssid if capture else None,
    )

    if not plan.stages:
        warnings.append("No hay wordlists ni reglas disponibles en el sistema")

    return AnalyzeResponse(plan=plan, hash_info=hash_info, warnings=warnings)


# ===================================================================
# CrackingJobs CRUD
# ===================================================================


@router.get("/jobs", response_model=list[CrackingJobRead])
def list_cracking_jobs(
    engagement_id: int | None = Query(None, ge=1),
    status: str | None = Query(None, max_length=32),
    db: Session = Depends(get_db),  # noqa: B008
) -> list[CrackingJob]:
    """Lista los trabajos de cracking."""
    service = get_cracking_service()
    return service.list_jobs(db, engagement_id=engagement_id, status=status)


@router.post("/jobs", response_model=CrackingJobRead, status_code=status.HTTP_201_CREATED)
def create_cracking_job(
    artifact_id: int = Query(..., ge=1),
    strategy: str = Query("dictionary", max_length=32),
    engagement_id: int | None = Query(None, ge=1),
    db: Session = Depends(get_db),  # noqa: B008
) -> CrackingJob:
    """Crea un nuevo CrackingJob para un handshake."""
    artifact = db.get(HandshakeArtifact, artifact_id)
    if artifact is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"HandshakeArtifact #{artifact_id} no encontrado",
        )

    service = get_cracking_service()
    return service.create_cracking_job(
        db,
        artifact_id=artifact_id,
        strategy=strategy,
        engagement_id=engagement_id,
    )


@router.get("/jobs/{job_id}", response_model=CrackingJobRead)
def get_cracking_job(
    job_id: int,
    db: Session = Depends(get_db),  # noqa: B008
) -> CrackingJob:
    """Obtiene el detalle de un CrackingJob."""
    service = get_cracking_service()
    job = service.get_job(db, job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"CrackingJob #{job_id} no encontrado",
        )
    return job


# ===================================================================
# Ejecución
# ===================================================================


@router.post("/jobs/{job_id}/start", response_model=StartJobResponse)
async def start_cracking_job(
    job_id: int,
    engagement_id: int = Query(..., ge=1),
    preferred_dicts: list[str] | None = Query(None),
    preferred_rules: list[str] | None = Query(None),
    max_total_time: int = Query(3600, ge=60, le=86400),
    db: Session = Depends(get_db),  # noqa: B008
) -> StartJobResponse:
    """Ejecuta el plan de cracking para un CrackingJob."""
    service = get_cracking_service()
    job = service.get_job(db, job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"CrackingJob #{job_id} no encontrado",
        )

    artifact_id = job.artifact_id
    if artifact_id is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"CrackingJob #{job_id} no tiene un handshake asociado",
        )
    artifact = db.get(HandshakeArtifact, artifact_id)
    if artifact is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"HandshakeArtifact #{job.artifact_id} no encontrado",
        )

    try:
        service.validate_artifact(artifact)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e

    invalid = _validate_preferred_paths(preferred_dicts, "diccionario") + _validate_preferred_paths(
        preferred_rules, "regla"
    )
    if invalid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="; ".join(invalid),
        )

    capture = artifact.capture
    plan = _planner.build_plan(
        job_id=job_id,
        artifact_id=artifact_id,
        hash_file_path=artifact.hash22000_path or "",
        max_total_time=max_total_time,
        preferred_dicts=preferred_dicts,
        preferred_rules=preferred_rules,
        cap_file_path=capture.path if capture else None,
        bssid=capture.bssid if capture else None,
    )

    try:
        queued_job = service.queue_plan(db, plan, engagement_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return StartJobResponse(job_id=job_id, status=queued_job.status)


@router.post("/jobs/{job_id}/cancel")
async def cancel_cracking_job(
    job_id: int,
    db: Session = Depends(get_db),  # noqa: B008
) -> dict[str, str]:
    """Cancela un CrackingJob pendiente o en ejecución."""
    service = get_cracking_service()
    job = await service.cancel_active_job(db, job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"CrackingJob #{job_id} no encontrado",
        )
    return {"status": "cancelled"}


# ===================================================================
# Hash info
# ===================================================================


@router.get("/handshakes/{artifact_id}/hashinfo", response_model=HashInfo)
def get_handshake_hash_info(
    artifact_id: int,
    db: Session = Depends(get_db),  # noqa: B008
) -> HashInfo:
    """Obtiene información del hash .22000 de un handshake."""
    artifact = db.get(HandshakeArtifact, artifact_id)
    if artifact is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"HandshakeArtifact #{artifact_id} no encontrado",
        )

    service = get_cracking_service()
    info = service.get_hash_info(artifact)
    if info is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No se pudo leer el archivo .22000 del handshake",
        )
    return info
