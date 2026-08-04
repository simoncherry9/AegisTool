"""CLI Typer para AegisWiFi (minuta §33).

Solo se exponen aquí los comandos viables en esta fase (engagement/scope/serve).
Los de hardware/captura/cracking se añaden cuando existan sus módulos.
"""

from __future__ import annotations

import json
from pathlib import Path

import typer

from aegiswifi import __version__
from aegiswifi.core.config import get_settings
from aegiswifi.database.engine import get_sessionmaker
from aegiswifi.engagements import service as engagements_service
from aegiswifi.scope import service as scope_service

app = typer.Typer(
    name="aegiswifi",
    help="AegisWiFi — plataforma de auditoría inalámbrica.",
    no_args_is_help=True,
)


@app.command()
def version() -> None:
    """Muestra versión y entorno."""
    typer.echo(f"aegiswifi {__version__} ({get_settings().environment})")


@app.command()
def serve(
    host: str = typer.Option(None, help="Host (default: 127.0.0.1)"),
    port: int = typer.Option(None, help="Puerto (default: 8000)"),
) -> None:
    """Levanta la API (uvicorn). Por defecto en 127.0.0.1:8000 (minuta §34)."""
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "aegiswifi.main:app",
        host=host or settings.api_host,
        port=port or settings.api_port,
        reload=settings.is_dev,
    )


engagement_app = typer.Typer(no_args_is_help=True)
scope_app = typer.Typer(no_args_is_help=True)
job_app = typer.Typer(no_args_is_help=True)
evidence_app = typer.Typer(no_args_is_help=True)
interface_app = typer.Typer(no_args_is_help=True)
cracking_app = typer.Typer(no_args_is_help=True)
validation_app = typer.Typer(no_args_is_help=True)
from aegiswifi.discovery import cli as discovery_cli

app.add_typer(engagement_app, name="engagement")
app.add_typer(scope_app, name="scope")
app.add_typer(job_app, name="job")
app.add_typer(evidence_app, name="evidence")
app.add_typer(interface_app, name="interface")
app.add_typer(cracking_app, name="cracking")
app.add_typer(validation_app, name="validation")
app.add_typer(discovery_cli.discovery_app, name="discovery")


@engagement_app.command("create")
def engagement_create(
    name: str = typer.Option(..., "--name"),
    client: str = typer.Option(..., "--client"),
    operator: str = typer.Option(..., "--operator"),
) -> None:
    """Crea un engagement en estado DRAFT."""
    from aegiswifi.engagements.schemas import EngagementCreate

    session = get_sessionmaker()()
    try:
        e = engagements_service.create_engagement(
            session, EngagementCreate(name=name, client=client, operator=operator)
        )
        typer.echo(json.dumps({"id": e.id, "code": e.code, "status": e.status}, indent=2))
    finally:
        session.close()


@engagement_app.command("activate")
def engagement_activate(id: int = typer.Argument(...)) -> None:
    """Activa un engagement."""
    session = get_sessionmaker()()
    try:
        e = engagements_service.activate(session, id)
        typer.echo(json.dumps({"id": e.id, "code": e.code, "status": e.status}, indent=2))
    finally:
        session.close()


@scope_app.command("import")
def scope_import(
    authorization: Path = typer.Argument(..., help="Archivo YAML de alcance"),
    engagement_id: int = typer.Option(..., "--engagement", "-e"),
) -> None:
    """Importa el alcance autorizado a un engagement (minuta §33)."""
    session = get_sessionmaker()()
    try:
        engagement, scope = scope_service.import_scope(session, engagement_id, authorization)
        typer.echo(
            json.dumps(
                {
                    "engagement": engagement.code,
                    "ssids": scope.scope.allowed_ssids,
                    "bssids": scope.scope.allowed_bssids,
                    "permissions": scope.permissions.model_dump(),
                },
                indent=2,
            )
        )
    finally:
        session.close()


# ------------------------------------------------------------------
# Comandos de trabajos
# ------------------------------------------------------------------


@job_app.command("list")
def job_list(
    engagement_id: int | None = typer.Option(
        None, "--engagement", "-e", help="Filtrar por engagement"
    ),
    status: str | None = typer.Option(None, "--status", "-s", help="Filtrar por estado"),
    limit: int = typer.Option(100, "--limit", "-l", help="Máx resultados"),
) -> None:
    """Lista trabajos."""
    from aegiswifi.database.models import JobStatus
    from aegiswifi.jobs import service as jobs_service

    status_enum = JobStatus(status) if status else None
    session = get_sessionmaker()()
    try:
        jobs = jobs_service.list_jobs(
            session, engagement_id=engagement_id, status=status_enum, limit=limit
        )
        rows = [
            {
                "id": j.id,
                "kind": j.kind,
                "status": j.status,
                "priority": j.priority,
                "progress": j.progress,
                "error": j.error_message,
            }
            for j in jobs
        ]
        typer.echo(json.dumps(rows, indent=2, default=str))
    finally:
        session.close()


@job_app.command("status")
def job_status(job_id: int = typer.Argument(...)) -> None:
    """Muestra estado detallado de un trabajo."""
    from aegiswifi.jobs import service as jobs_service

    session = get_sessionmaker()()
    try:
        job = jobs_service.get_job(session, job_id)
        typer.echo(
            json.dumps(
                {
                    "id": job.id,
                    "kind": job.kind,
                    "status": job.status,
                    "priority": job.priority,
                    "progress": job.progress,
                    "error_message": job.error_message,
                    "group_id": job.group_id,
                    "timeout_seconds": job.timeout_seconds,
                    "worker_pid": job.worker_pid,
                    "heartbeat_at": str(job.heartbeat_at) if job.heartbeat_at else None,
                    "started_at": str(job.started_at) if job.started_at else None,
                    "finished_at": str(job.finished_at) if job.finished_at else None,
                    "log_path": job.log_path,
                    "sha256": job.sha256,
                    "parameters": job.parameters,
                    "result_summary": job.result_summary,
                    "created_at": str(job.created_at),
                    "updated_at": str(job.updated_at),
                },
                indent=2,
                default=str,
            )
        )
    finally:
        session.close()


@job_app.command("events")
def job_events(job_id: int = typer.Argument(...)) -> None:
    """Muestra historial de eventos de un trabajo."""
    from aegiswifi.jobs import service as jobs_service

    session = get_sessionmaker()()
    try:
        events = jobs_service.list_job_events(session, job_id)
        rows = [
            {
                "id": e.id,
                "from": e.from_status,
                "to": e.to_status,
                "message": e.message,
                "at": str(e.created_at),
            }
            for e in events
        ]
        typer.echo(json.dumps(rows, indent=2, default=str))
    finally:
        session.close()


@job_app.command("cancel")
def job_cancel(
    job_id: int = typer.Argument(...),
    message: str = typer.Option(None, "--message", "-m", help="Motivo de cancelación"),
) -> None:
    """Cancela un trabajo."""
    from aegiswifi.jobs import service as jobs_service

    session = get_sessionmaker()()
    try:
        job = jobs_service.cancel_job(session, job_id, message=message or None)
        typer.echo(json.dumps({"id": job.id, "status": job.status}, indent=2))
    finally:
        session.close()


# ------------------------------------------------------------------
# Comandos de evidencia
# ------------------------------------------------------------------


@evidence_app.command("list")
def evidence_list(
    engagement_id: int = typer.Option(..., "--engagement", "-e", help="ID del engagement"),
    job_id: int | None = typer.Option(None, "--job", "-j", help="Filtrar por trabajo"),
    category: str | None = typer.Option(None, "--category", "-c", help="Filtrar por categoría"),
    limit: int = typer.Option(100, "--limit", "-l", help="Máx resultados"),
) -> None:
    """Lista evidencia de un engagement."""
    from aegiswifi.evidence import service as evidence_service

    session = get_sessionmaker()()
    try:
        items = evidence_service.list_evidence(
            session,
            engagement_id=engagement_id,
            job_id=job_id,
            category=category,
            limit=limit,
        )
        rows = [
            {
                "id": c.id,
                "category": c.category,
                "format": c.format,
                "sha256": c.sha256,
                "original_filename": c.original_filename,
                "size_bytes": c.size_bytes,
                "tool": c.tool,
                "created_at": str(c.created_at),
            }
            for c in items
        ]
        typer.echo(json.dumps(rows, indent=2, default=str))
    finally:
        session.close()


@evidence_app.command("inspect")
def evidence_inspect(id: int = typer.Argument(...)) -> None:
    """Muestra metadata detallada de una evidencia."""
    from aegiswifi.evidence import service as evidence_service

    session = get_sessionmaker()()
    try:
        c = evidence_service.get_evidence(session, id)
        typer.echo(
            json.dumps(
                {
                    "id": c.id,
                    "engagement_id": c.engagement_id,
                    "job_id": c.job_id,
                    "category": c.category,
                    "path": c.path,
                    "format": c.format,
                    "sha256": c.sha256,
                    "original_filename": c.original_filename,
                    "size_bytes": c.size_bytes,
                    "interface": c.interface,
                    "channel": c.channel,
                    "bssid": c.bssid,
                    "ssid": c.ssid,
                    "tool": c.tool,
                    "tool_version": c.tool_version,
                    "metadata": c.metadata,
                    "derived_from_id": c.derived_from_id,
                    "started_at": str(c.started_at) if c.started_at else None,
                    "finished_at": str(c.finished_at) if c.finished_at else None,
                    "created_at": str(c.created_at),
                },
                indent=2,
                default=str,
            )
        )
    finally:
        session.close()


@evidence_app.command("verify")
def evidence_verify(id: int = typer.Argument(...)) -> None:
    """Verifica integridad SHA-256 de una evidencia."""
    from aegiswifi.evidence import service as evidence_service
    from aegiswifi.evidence.store import EvidenceStore

    session = get_sessionmaker()()
    try:
        c = evidence_service.get_evidence(session, id)
        path = Path(c.path)
        if not path.exists():
            typer.echo(json.dumps({"error": "archivo no encontrado en disco"}, indent=2))
            raise typer.Exit(code=1)
        if not c.sha256:
            typer.echo(json.dumps({"error": "evidencia no tiene SHA-256 registrado"}, indent=2))
            raise typer.Exit(code=1)
        valid = EvidenceStore.verify_integrity(path, c.sha256)
        typer.echo(
            json.dumps(
                {
                    "id": c.id,
                    "path": c.path,
                    "expected_sha256": c.sha256,
                    "valid": valid,
                },
                indent=2,
            )
        )
        if not valid:
            raise typer.Exit(code=1)
    finally:
        session.close()


# ------------------------------------------------------------------
# Comandos de interfaces
# ------------------------------------------------------------------


@interface_app.command("list")
def interface_list() -> None:
    """Lista interfaces inal�mbricas detectadas."""
    import asyncio

    from aegiswifi.interfaces import service as iface_service

    interfaces = asyncio.run(iface_service.list_all_interfaces())
    rows = [
        {
            "name": i.name,
            "phy": i.phy,
            "mac": i.mac,
            "driver": i.driver,
            "type": i.type,
            "state": i.state,
            "monitor_mode": i.monitor_mode,
            "bands": i.bands,
        }
        for i in interfaces
    ]
    typer.echo(json.dumps(rows, indent=2, default=str))


@interface_app.command("info")
def interface_info(name: str = typer.Argument(...)) -> None:
    """Muestra informaci�n detallada de una interfaz."""
    import asyncio

    from aegiswifi.interfaces import service as iface_service

    iface = asyncio.run(iface_service.get_interface(name))
    if iface is None:
        typer.echo(json.dumps({"error": f"interfaz '{name}' no encontrada"}, indent=2))
        raise typer.Exit(code=1)
    typer.echo(iface.model_dump_json(indent=2))


@interface_app.command("prepare")
def interface_prepare(
    name: str = typer.Argument(..., help="Nombre de la interfaz f�sica"),
    virtual: bool = typer.Option(False, "--virtual", "-v", help="Crear interfaz virtual"),
) -> None:
    """Prepara una interfaz para auditor�a (monitor mode + inyecci�n)."""
    import asyncio

    from aegiswifi.interfaces import service as iface_service

    try:
        result = asyncio.run(iface_service.prepare_interface(name, create_virtual=virtual))
        typer.echo(result.model_dump_json(indent=2))
    except RuntimeError as e:
        typer.echo(json.dumps({"error": str(e)}, indent=2))
        raise typer.Exit(code=1) from e


@interface_app.command("restore")
def interface_restore(name: str = typer.Argument(..., help="Nombre de la interfaz")) -> None:
    """Restaura una interfaz a su estado original."""
    import asyncio

    from aegiswifi.interfaces import service as iface_service

    result = asyncio.run(iface_service.restore_interface(name))
    typer.echo(result.model_dump_json(indent=2))
    if not result.restored:
        raise typer.Exit(code=1)


@interface_app.command("diagnose")
def interface_diagnose(
    name: str | None = typer.Argument(None, help="Interfaz a diagnosticar (opcional)"),
) -> None:
    """Diagn�stico del sistema de interfaces."""
    import asyncio

    from aegiswifi.interfaces import service as iface_service

    result = asyncio.run(iface_service.diagnose_interface(name))
    typer.echo(result.model_dump_json(indent=2))
    if result.issues:
        raise typer.Exit(code=1)


# ===================================================================
# Cracking commands
# ===================================================================


@cracking_app.command("dicts")
def cracking_dicts() -> None:
    """Lista wordlists disponibles."""
    from aegiswifi.cracking.dictionary import DictionaryManager

    manager = DictionaryManager()
    dicts = manager.scan_all()
    if not dicts:
        typer.echo("No se encontraron wordlists.")
        raise typer.Exit(code=1)
    for d in dicts:
        size_mb = d.size_bytes / (1024 * 1024)
        typer.echo(f"{d.name:40s} {size_mb:>8.1f} MB  {d.path}")
    typer.echo(f"\nTotal: {len(dicts)} wordlist(s)")


@cracking_app.command("rules")
def cracking_rules() -> None:
    """Lista reglas de hashcat disponibles."""
    from aegiswifi.cracking.rules import RulesManager

    manager = RulesManager()
    rules = manager.scan_all()
    if not rules:
        typer.echo("No se encontraron archivos de reglas.")
        raise typer.Exit(code=1)
    for r in rules:
        size_kb = r.size_bytes / 1024
        typer.echo(f"{r.name:40s} {size_kb:>8.1f} KB  {r.path}")
    typer.echo(f"\nTotal: {len(rules)} rule file(s)")


@cracking_app.command("analyze")
def cracking_analyze(
    artifact_id: int = typer.Argument(..., help="ID del HandshakeArtifact"),
) -> None:
    """Analiza un handshake y genera un plan de cracking."""

    from aegiswifi.cracking.dictionary import DictionaryManager
    from aegiswifi.cracking.planner import CrackingPlanner
    from aegiswifi.cracking.rules import RulesManager
    from aegiswifi.cracking.service import get_cracking_service
    from aegiswifi.database.engine import get_sessionmaker

    SessionLocal = get_sessionmaker()
    with SessionLocal() as db:
        service = get_cracking_service()
        from aegiswifi.database.models import HandshakeArtifact

        artifact = db.get(HandshakeArtifact, artifact_id)
        if artifact is None:
            typer.echo(f"Error: HandshakeArtifact #{artifact_id} no encontrado.")
            raise typer.Exit(code=1)

        try:
            service.validate_artifact(artifact)
        except ValueError as e:
            typer.echo(f"Error: {e}")
            raise typer.Exit(code=1) from e

        hash_info = service.get_hash_info(artifact)
        if hash_info:
            typer.echo(f"SSID: {hash_info.ssid or 'N/A'}")
            typer.echo(f"BSSID: {hash_info.bssid or 'N/A'}")
            typer.echo(f"Tipo: {hash_info.kind}")
            typer.echo("")

        dict_manager = DictionaryManager()
        rules_manager = RulesManager()
        planner = CrackingPlanner(dict_manager, rules_manager)
        plan = planner.build_plan(
            job_id=0,
            artifact_id=artifact_id,
            hash_file_path=artifact.hash22000_path or "",
        )

        typer.echo(f"Plan de {len(plan.stages)} etapa(s):")
        for i, stage in enumerate(plan.stages, 1):
            timeout_min = stage.timeout_seconds / 60 if stage.timeout_seconds else 0
            typer.echo(f"  {i}. {stage.mode.value:30s} (timeout: {timeout_min:.0f} min)")
            if stage.dictionary_path:
                typer.echo(f"     Diccionario: {stage.dictionary_path}")
            if stage.rules_path:
                typer.echo(f"     Reglas: {stage.rules_path}")
            if stage.mask:
                typer.echo(f"     Máscara: {stage.mask}")

        if not plan.stages:
            typer.echo("  (sin etapas — no hay wordlists/reglas disponibles)")


@cracking_app.command("list")
def cracking_list(
    engagement_id: int | None = typer.Option(
        None, "--engagement", "-e", help="Filtrar por engagement"
    ),
) -> None:
    """Lista trabajos de cracking."""
    from aegiswifi.cracking.service import get_cracking_service
    from aegiswifi.database.engine import get_sessionmaker

    SessionLocal = get_sessionmaker()
    with SessionLocal() as db:
        service = get_cracking_service()
        jobs = service.list_jobs(db, engagement_id=engagement_id)

    if not jobs:
        typer.echo("No hay trabajos de cracking.")
        return

    for j in jobs:
        typer.echo(
            f"#{j.id:5d}  {j.strategy:20s}  {j.status:15s}  "
            f"progress={j.progress or 0:.0%}  speed={j.speed or 0} H/s  "
            f"recovered={'YES' if j.recovered else 'NO'}"
        )
    typer.echo(f"\nTotal: {len(jobs)} job(s)")


@cracking_app.command("status")
def cracking_status(
    job_id: int = typer.Argument(..., help="ID del CrackingJob"),
) -> None:
    """Muestra detalle de un CrackingJob."""
    import json as _json

    from aegiswifi.cracking.service import get_cracking_service
    from aegiswifi.database.engine import get_sessionmaker

    SessionLocal = get_sessionmaker()
    with SessionLocal() as db:
        service = get_cracking_service()
        job = service.get_job(db, job_id)

    if job is None:
        typer.echo(f"Error: CrackingJob #{job_id} no encontrado.")
        raise typer.Exit(code=1)

    typer.echo(
        _json.dumps(
            {
                "id": job.id,
                "artifact_id": job.artifact_id,
                "strategy": job.strategy,
                "status": job.status,
                "progress": job.progress,
                "speed": job.speed,
                "recovered": job.recovered,
                "keyspace": job.keyspace,
                "started_at": str(job.started_at) if job.started_at else None,
                "finished_at": str(job.finished_at) if job.finished_at else None,
            },
            indent=2,
        )
    )


@cracking_app.command("start")
def cracking_start(
    job_id: int = typer.Argument(..., help="ID del CrackingJob"),
    engagement_id: int = typer.Option(..., "--engagement", "-e", help="ID del Engagement"),
) -> None:
    """Ejecuta el plan de cracking para un CrackingJob."""
    import asyncio

    from aegiswifi.cracking.dictionary import DictionaryManager
    from aegiswifi.cracking.planner import CrackingPlanner
    from aegiswifi.cracking.rules import RulesManager
    from aegiswifi.cracking.service import get_cracking_service
    from aegiswifi.database.engine import get_sessionmaker
    from aegiswifi.database.models import HandshakeArtifact

    SessionLocal = get_sessionmaker()
    with SessionLocal() as db:
        service = get_cracking_service()
        job = service.get_job(db, job_id)
        if job is None:
            typer.echo(f"Error: CrackingJob #{job_id} no encontrado.")
            raise typer.Exit(code=1)

        artifact_id = job.artifact_id
        if artifact_id is None:
            typer.echo(f"Error: CrackingJob #{job_id} no tiene un handshake asociado.")
            raise typer.Exit(code=1)
        artifact = db.get(HandshakeArtifact, artifact_id)
        if artifact is None:
            typer.echo(f"Error: HandshakeArtifact #{job.artifact_id} no encontrado.")
            raise typer.Exit(code=1)

        try:
            service.validate_artifact(artifact)
        except ValueError as e:
            typer.echo(f"Error: {e}")
            raise typer.Exit(code=1) from e

        dict_manager = DictionaryManager()
        rules_manager = RulesManager()
        planner = CrackingPlanner(dict_manager, rules_manager)
        plan = planner.build_plan(
            job_id=job_id,
            artifact_id=artifact_id,
            hash_file_path=artifact.hash22000_path or "",
        )

        typer.echo(f"Ejecutando plan de {len(plan.stages)} etapa(s)...")
        result = asyncio.run(service.execute_plan(plan, engagement_id=engagement_id, session=db))

    typer.echo(result.model_dump_json(indent=2))
    if result.cracked:
        typer.echo(f"\n✓ CONTRASEÑA RECUPERADA: {result.password}")
    else:
        typer.echo("\n✗ No se recuperó la contraseña.")


@cracking_app.command("cancel")
def cracking_cancel(
    job_id: int = typer.Argument(..., help="ID del CrackingJob"),
) -> None:
    """Cancela un CrackingJob pendiente o en ejecución."""
    from aegiswifi.cracking.service import get_cracking_service
    from aegiswifi.database.engine import get_sessionmaker

    SessionLocal = get_sessionmaker()
    with SessionLocal() as db:
        service = get_cracking_service()
        job = service.cancel_job(db, job_id)

    if job is None:
        typer.echo(f"Error: CrackingJob #{job_id} no encontrado.")
        raise typer.Exit(code=1)

    typer.echo(f"CrackingJob #{job_id} cancelado (status={job.status}).")


# ===================================================================
# Validation (handshake) commands
# ===================================================================


@validation_app.command("validate")
def validation_validate(
    capture_id: int | None = typer.Option(None, "--capture", "-c", help="ID de la captura"),
    file_path: str | None = typer.Option(None, "--file", "-f", help="Ruta al archivo .pcapng"),
    force: bool = typer.Option(False, "--force", help="Reprocesar aunque ya exista artifact"),
) -> None:
    """Valida una captura — analiza handshakes EAPOL/PMKID."""
    import asyncio
    import json as _json

    from aegiswifi.database.engine import get_sessionmaker
    from aegiswifi.database.models import Capture
    from aegiswifi.validation.service import get_validation_service

    if not capture_id and not file_path:
        typer.echo("Error: Se requiere --capture o --file")
        raise typer.Exit(code=1)

    SessionLocal = get_sessionmaker()
    capture: Capture | None = None

    with SessionLocal() as db:
        if capture_id:
            capture = db.get(Capture, capture_id)
            if capture is None:
                typer.echo(f"Error: Capture #{capture_id} no encontrado.")
                raise typer.Exit(code=1)

        service = get_validation_service()
        result = asyncio.run(
            service.validate_capture(
                capture=capture,
                file_path=file_path,
                db_session=db,
                force=force,
            )
        )

    typer.echo(_json.dumps(result.model_dump(exclude_none=True), indent=2))
    if result.validated:
        typer.echo(f"\n✓ Handshake validado — calidad: {result.quality.value}")
        if result.eapol.has_full_handshake:
            typer.echo("  Handshake completo detectado")
        if result.pmkid.detected:
            typer.echo("  PMKID detectado")
    else:
        typer.echo(f"\n✗ Handshake NO validado — calidad: {result.quality.value}")
        if result.errors:
            for err in result.errors:
                typer.echo(f"  Error: {err}")
        raise typer.Exit(code=1)


@validation_app.command("list")
def validation_list(
    quality: str | None = typer.Option(None, "--quality", "-q", help="Filtrar por calidad"),
    limit: int = typer.Option(100, "--limit", "-l", help="Máx resultados"),
) -> None:
    """Lista HandshakeArtifacts validados."""
    import json as _json

    from aegiswifi.database.engine import get_sessionmaker
    from aegiswifi.validation.service import get_validation_service

    SessionLocal = get_sessionmaker()
    with SessionLocal() as db:
        service = get_validation_service()

        from sqlalchemy import select

        from aegiswifi.database.models import HandshakeArtifact

        stmt = select(HandshakeArtifact)
        if quality:
            stmt = stmt.where(HandshakeArtifact.quality == quality.upper())
        stmt = stmt.order_by(HandshakeArtifact.id.desc()).limit(limit)
        artifacts = list(db.scalars(stmt).all())

        if not artifacts:
            typer.echo("No hay artifacts de validación.")
            return

        for a in artifacts:
            report = service.build_report(a)
            typer.echo(_json.dumps(report, indent=2, default=str))
            typer.echo("---")

        typer.echo(f"Total: {len(artifacts)} artifact(s)")


@validation_app.command("report")
def validation_report(
    artifact_id: int = typer.Argument(..., help="ID del HandshakeArtifact"),
) -> None:
    """Muestra reporte detallado de un HandshakeArtifact."""
    import json as _json

    from aegiswifi.database.engine import get_sessionmaker
    from aegiswifi.database.models import HandshakeArtifact
    from aegiswifi.validation.service import get_validation_service

    SessionLocal = get_sessionmaker()
    with SessionLocal() as db:
        artifact = db.get(HandshakeArtifact, artifact_id)
        if artifact is None:
            typer.echo(f"Error: HandshakeArtifact #{artifact_id} no encontrado.")
            raise typer.Exit(code=1)

        service = get_validation_service()
        report = service.build_report(artifact)

    typer.echo(_json.dumps(report, indent=2, default=str))


@validation_app.command("reprocess")
def validation_reprocess(
    artifact_id: int = typer.Argument(..., help="ID del HandshakeArtifact"),
) -> None:
    """Reprocesa un HandshakeArtifact existente."""
    import asyncio
    import json as _json

    from aegiswifi.database.engine import get_sessionmaker
    from aegiswifi.database.models import Capture, HandshakeArtifact
    from aegiswifi.validation.service import get_validation_service

    SessionLocal = get_sessionmaker()
    with SessionLocal() as db:
        artifact = db.get(HandshakeArtifact, artifact_id)
        if artifact is None:
            typer.echo(f"Error: HandshakeArtifact #{artifact_id} no encontrado.")
            raise typer.Exit(code=1)

        capture = db.get(Capture, artifact.capture_id) if artifact.capture_id else None
        service = get_validation_service()
        result = asyncio.run(service.validate_capture(capture=capture, db_session=db, force=True))

    typer.echo(_json.dumps(result.model_dump(exclude_none=True), indent=2))
    if result.validated:
        typer.echo(f"\n✓ Handshake reprocesado — calidad: {result.quality.value}")
    else:
        typer.echo(f"\n✗ Handshake NO validado — calidad: {result.quality.value}")
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
