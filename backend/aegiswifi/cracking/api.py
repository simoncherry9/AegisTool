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

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from aegiswifi.core.exceptions import NotFound, ScopeViolation
from aegiswifi.cracking.dictionary import DictionaryManager
from aegiswifi.cracking.planner import CrackingPlanner
from aegiswifi.cracking.rules import RulesManager
from aegiswifi.cracking.schemas import (
    AttackMode,
    CrackingJobRead,
    CrackingPlan,
    CrackingProgress,
    CrackingResult,
    DictionaryInfo,
    HashInfo,
    RuleInfo,
)
from aegiswifi.cracking.service import CrackingService, get_cracking_service
from aegiswifi.database.engine import get_db
from aegiswifi.database.models import CrackingJob, HandshakeArtifact

router = APIRouter(prefix="/cracking", tags=["cracking"])

# Helpers reutilizables (singletons ligeros).
_dict_manager = DictionaryManager()
_rules_manager = RulesManager()
_planner = CrackingPlanner(_dict_manager, _rules_manager)


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
    result: CrackingResult


# ===================================================================
# Dictionaries & Rules
# ===================================================================


class CustomWordlistCreate(BaseModel):
    name: str
    words: list[str]


@router.get("/dictionaries", response_model=list[DictionaryInfo])
def list_dictionaries(
    force_rescan: bool = Query(False),
) -> list[DictionaryInfo]:
    """Lista las wordlists disponibles en el sistema."""
    return _dict_manager.scan_all(force=force_rescan)


@router.post("/dictionaries/custom", response_model=DictionaryInfo, status_code=status.HTTP_201_CREATED)
def create_custom_dictionary(body: CustomWordlistCreate) -> DictionaryInfo:
    """Crea un diccionario de palabras personalizado."""
    if not body.words:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La lista de palabras no puede estar vacía")
    return _dict_manager.create_custom_wordlist(body.name, body.words)


@router.delete("/dictionaries/custom/{name}", status_code=status.HTTP_204_NO_CONTENT)
def delete_custom_dictionary(name: str) -> None:
    """Elimina un diccionario personalizado."""
    deleted = _dict_manager.delete_custom_wordlist(name)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Diccionario '{name}' no encontrado")


@router.get("/rules", response_model=list[RuleInfo])
def list_rules(
    force_rescan: bool = Query(False),
) -> list[RuleInfo]:
    """Lista los archivos de reglas disponibles en el sistema."""
    return _rules_manager.scan_all(force=force_rescan)


@router.get("/dictionaries/system")
def list_system_wordlists() -> list[str]:
    from aegiswifi.cracking.dictionary import scan_system_wordlists
    return scan_system_wordlists()


class CustomWordlistReq(BaseModel):
    name: str
    words: list[str]


@router.post("/dictionaries/custom")
def create_custom_wordlist_route(req: CustomWordlistReq):
    from aegiswifi.cracking.dictionary import create_custom_wordlist
    path = create_custom_wordlist(req.name, req.words)
    return {"path": path}


@router.delete("/dictionaries/custom/{name}")
def delete_custom_wordlist_route(name: str):
    from aegiswifi.cracking.dictionary import delete_custom_wordlist
    success = delete_custom_wordlist(name)
    if not success:
        raise HTTPException(status_code=404, detail="Wordlist not found")
    return {"status": "deleted"}


@router.get("/engines")
def list_engines():
    return ["hashcat", "john"]



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

    plan = _planner.build_plan(
        job_id=0,  # se asigna al crear el job
        artifact_id=artifact_id,
        hash_file_path=artifact.hash22000_path or "",
        max_total_time=max_total_time,
        preferred_dicts=preferred_dicts,
        preferred_rules=preferred_rules,
        skip_modes=skip_modes,
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

    artifact = db.get(HandshakeArtifact, job.artifact_id)
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

    plan = _planner.build_plan(
        job_id=job_id,
        artifact_id=job.artifact_id,
        hash_file_path=artifact.hash22000_path or "",
        max_total_time=max_total_time,
        preferred_dicts=preferred_dicts,
        preferred_rules=preferred_rules,
    )

    result = await service.execute_plan(plan, engagement_id=engagement_id, session=db)
    return StartJobResponse(job_id=job_id, result=result)


@router.post("/jobs/{job_id}/cancel")
def cancel_cracking_job(
    job_id: int,
    db: Session = Depends(get_db),  # noqa: B008
) -> dict[str, str]:
    """Cancela un CrackingJob pendiente o en ejecución."""
    service = get_cracking_service()
    job = service.cancel_job(db, job_id)
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
