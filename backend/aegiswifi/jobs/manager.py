"""Orquestador central de trabajos en background (minuta §26).

JobManager se ejecuta como tarea asíncrona dentro del *lifespan* de FastAPI:
  - Cola de prioridad asyncio.
  - Workers limitados por semáforo (``max_workers``).
  - Loop de heartbeats para detectar trabajos colgados.
  - Recuperación de trabajos pendientes al arrancar tras un reinicio.
  - Integración con :class:`EventBus` para emitir eventos en tiempo real.

Uso (desde el lifespan)::

    manager = JobManager(session_factory=get_sessionmaker,
                         event_bus=event_bus, config=settings.jobs)
    await manager.start()
    ...
    await manager.stop()
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from aegiswifi.adapters.errors import ToolNotInstalled
from aegiswifi.adapters.registry import get_adapter
from aegiswifi.core.config import JobConfig
from aegiswifi.core.exceptions import ScopeViolation, ValidationFailed
from aegiswifi.database.models import Job as JobModel
from aegiswifi.database.models import JobStatus
from aegiswifi.engagements import service as engagements_service
from aegiswifi.evidence.store import EvidenceStore
from aegiswifi.jobs import service as jobs_service
from aegiswifi.jobs.event_bus import EventBus, JobEventEnvelope
from aegiswifi.jobs.statemachine import JobStateMachine
from aegiswifi.scope.policy import ScopeContext
from aegiswifi.scope.schemas import Limits, Permissions, ScopeBlock

SessionFactory = Callable[[], Session]


class JobManager:
    """Gestiona la cola de trabajos, workers, heartbeats y recuperación."""

    def __init__(
        self,
        session_factory: SessionFactory,
        event_bus: EventBus,
        config: JobConfig,
    ) -> None:
        self._session_factory = session_factory
        self._event_bus = event_bus
        self._config = config

        # Cola de prioridad: (priority, job_id); menor priority = más urgente.
        self._queue: asyncio.PriorityQueue[tuple[int, int]] = asyncio.PriorityQueue()
        self._active_jobs: dict[int, asyncio.Task[Any]] = {}
        self._semaphore = asyncio.Semaphore(config.max_workers)
        self._running = False

        self._consumer_task: asyncio.Task[None] | None = None
        self._heartbeat_task: asyncio.Task[None] | None = None

    # ------------------------------------------------------------------
    # Ciclo de vida
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Inicia el gestor: recupera trabajos pendientes y arranca loops."""
        self._running = True
        recovered = await asyncio.to_thread(self._recover_pending_jobs)
        self._consumer_task = asyncio.create_task(self._consumer_loop())
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        for job_id in recovered:
            await self._queue.put((0, job_id))

    async def stop(self) -> None:
        """Detiene el gestor: cancela tareas activas y limpia trabajos en ejecución."""
        self._running = False

        # Cancelar consumer y heartbeat.
        if self._consumer_task is not None:
            self._consumer_task.cancel()
        if self._heartbeat_task is not None:
            self._heartbeat_task.cancel()

        # Cancelar trabajos activos.
        for job_id, task in list(self._active_jobs.items()):
            task.cancel()
            try:  # noqa: SIM105 — suppress() no soporta await
                await asyncio.wait_for(task, timeout=5.0)
            except (TimeoutError, asyncio.CancelledError):
                pass

            # Marcar como FAILED en BD.
            def _fail_job(jid: int) -> None:
                session = self._session_factory()
                try:
                    jobs_service.transition_job(
                        session, jid, JobStatus.FAILED, message="detenido por cierre del sistema"
                    )
                finally:
                    session.close()

            await asyncio.to_thread(_fail_job, job_id)

        self._active_jobs.clear()

    # ------------------------------------------------------------------
    # Interfaz pública
    # ------------------------------------------------------------------

    async def enqueue(self, job_id: int) -> None:
        """Encola un trabajo existente (debe estar en estado CREATED o QUEUED)."""

        # Validar en un thread (DB sync).
        def _validate(jid: int) -> tuple[int, int]:
            session = self._session_factory()
            try:
                job = jobs_service.get_job(session, jid)
                current = JobStatus(job.status)
                if current not in (JobStatus.CREATED, JobStatus.QUEUED):
                    raise ValidationFailed(
                        f"trabajo {jid} no puede encolarse (estado: {current.value})"
                    )
                return (job.priority, job.timeout_seconds)
            finally:
                session.close()

        priority, _ = await asyncio.to_thread(_validate, job_id)
        await self._queue.put(
            (-priority, job_id)
        )  # negativa porque PriorityQueue ordena ascendente

    async def cancel_job(self, job_id: int) -> None:
        """Cancela un trabajo: si está en cola lo remueve; si corre cancela la tarea."""
        # Si está corriendo, cancelar la tarea asyncio.
        task = self._active_jobs.get(job_id)
        if task is not None:
            task.cancel()
            return

        # Si está en cola... no podemos remover de PriorityQueue fácilmente.
        # Marcamos en BD, y el consumer loop lo detectará al desencolar.
        def _mark_cancelled(jid: int) -> None:
            session = self._session_factory()
            try:
                jobs_service.transition_job(
                    session, jid, JobStatus.CANCELLED, message="cancelado antes de ejecutar"
                )
            finally:
                session.close()

        await asyncio.to_thread(_mark_cancelled, job_id)

    def get_status(self) -> dict[str, int]:
        """Devuelve una foto del estado actual del gestor (acceso thread-safe para métricas)."""
        active = len(self._active_jobs)
        queued = self._queue.qsize()
        return {
            "active_workers": active,
            "queued_jobs": queued,
            "max_workers": self._config.max_workers,
            "available_slots": max(0, self._config.max_workers - active),
        }

    # ------------------------------------------------------------------
    # Loop de consumo de cola
    # ------------------------------------------------------------------

    async def _consumer_loop(self) -> None:
        while self._running:
            try:
                neg_priority, job_id = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except TimeoutError:
                continue

            # Verificar que el trabajo no haya sido cancelado mientras estaba en cola.
            def _check_cancelled(jid: int) -> JobModel | None:
                session = self._session_factory()
                try:
                    job = jobs_service.get_job(session, jid)
                    if JobStatus(job.status) == JobStatus.CANCELLED:
                        return None
                    return job
                finally:
                    session.close()

            job = await asyncio.to_thread(_check_cancelled, job_id)
            if job is None:
                continue

            # Adquirir un slot de worker.
            await self._semaphore.acquire()
            task = asyncio.create_task(self._execute_job(job.id))
            self._active_jobs[job.id] = task
            task.add_done_callback(lambda _t: self._semaphore.release())
            task.add_done_callback(lambda _t, jid=job.id: self._active_jobs.pop(jid, None))  # type: ignore[misc]

    # ------------------------------------------------------------------
    # Ejecutor de trabajo (placeholder en Fase 1)
    # ------------------------------------------------------------------

    async def _execute_job(self, job_id: int) -> None:  # noqa: PLR0915
        """Ejecuta un trabajo real: ToolAdapter → ProcessSupervisor → EvidenceStore.

        En Fase 2 reemplaza el placeholder de Fase 1 con invocación real
        de herramientas externas a través del ToolAdapter correspondiente.
        """
        log = __import__("structlog").get_logger(__name__)

        job: JobModel | None = None
        adapter = None
        engagement_id = 0

        try:
            # --- Obtener trabajo y engagement desde DB ---
            def _get() -> tuple[JobModel, int, str]:
                session = self._session_factory()
                try:
                    j = jobs_service.get_job(session, job_id)
                    eng = engagements_service.get_engagement(session, j.engagement_id)
                    return j, eng.id, eng.code
                finally:
                    session.close()

            job, engagement_id, eng_code = await asyncio.to_thread(_get)
            # mypy narrowing — _get() siempre retorna un Job
            if not isinstance(job, JobModel):  # pragma: no cover
                raise RuntimeError("job no resuelto desde DB")

            # --- Transición a VALIDATING_SCOPE ---
            await self._transition(
                job_id, JobStatus.VALIDATING_SCOPE, "iniciando validación de alcance"
            )

            # --- Validar engagement y scope ---
            async def _validate() -> bool:
                session = self._session_factory()
                try:
                    j = jobs_service.get_job(session, job_id)
                    eng = engagements_service.get_engagement(session, j.engagement_id)
                    engagements_service.assert_active_and_not_expired(eng)
                    scope_ctx = ScopeContext(
                        engagement_code=eng.code,
                        valid_from=eng.start_date or datetime.now(UTC),
                        valid_until=eng.end_date or datetime.now(UTC) + timedelta(days=30),
                        scope=ScopeBlock(),
                        permissions=Permissions.model_validate(eng.permissions),
                        limits=Limits.model_validate(eng.limits),
                        operator=eng.operator,
                    )
                    jobs_service.validate_job_scope(j, scope_ctx)
                    log.info("job scope validated", job_id=job_id, kind=j.kind)
                    return True
                except (ScopeViolation, ValidationFailed) as e:
                    jobs_service.transition_job(session, job_id, JobStatus.FAILED, message=str(e))
                    return False
                finally:
                    session.close()

            valid = await asyncio.to_thread(_validate)
            if not valid:
                self._emit_event(
                    job_id,
                    engagement_id,
                    "job_failed",
                    {"error": "validación de alcance fallida"},
                )
                return

            # --- Transición a QUEUED → PREPARING ---
            await self._transition(job_id, JobStatus.QUEUED, "validación superada, encolado")
            await self._transition(
                job_id, JobStatus.PREPARING, "preparando adaptador de herramienta"
            )

            # --- Obtener adaptador del registry ---
            adapter = get_adapter(
                job.kind,
                job_id=job_id,
                engagement_id=engagement_id,
                event_bus=self._event_bus,
                config=self._config,
            )

            # --- Validar instalación de la herramienta ---
            installed = await adapter.validate_installation()
            if not installed:
                raise ToolNotInstalled(f"{adapter.tool_name} no está instalado en el sistema")

            version = await adapter.get_version()

            # --- Transición a RUNNING ---
            await self._transition(
                job_id,
                JobStatus.RUNNING,
                f"ejecutando {adapter.tool_name} {version}",
                started=True,
            )

            # --- Ejecutar adaptador ---
            result = await adapter.start(
                {
                    "timeout_seconds": job.timeout_seconds,
                    "options": job.parameters,
                }
            )

            # --- Parsear resultados ---
            parsed = await adapter.collect_results()

            # --- Almacenar evidencia (log de ejecución) ---
            evidence_store = EvidenceStore(
                evidence_dir=self._config.evidence_dir,
                session_factory=self._session_factory,
            )
            log_path = result.get("log_path", "")
            if log_path:
                capture = await evidence_store.store_artifact(
                    source_path=Path(log_path),
                    original_filename=f"job_{job_id}.log",
                    engagement_id=engagement_id,
                    job_id=job_id,
                    category="log",
                    format="log",
                    tool=adapter.tool_name,
                    tool_version=version,
                    metadata={
                        "exit_code": result.get("exit_code"),
                        "line_count": result.get("line_count"),
                    },
                )
            else:
                capture = None

            # --- Si hay archivo de captura en parámetros, almacenarlo ---
            params: dict[str, object] = job.parameters
            _output = params.get("output")
            output_file: str | None = str(_output) if isinstance(_output, str) else None
            if output_file and await asyncio.to_thread(os.path.exists, output_file):  # type: ignore[arg-type]
                fmt = "pcapng" if output_file.endswith(".pcapng") else "pcap"
                _interface = params.get("interface")
                _channel = params.get("channel")
                _bssid = params.get("bssid")
                _ssid = params.get("ssid")
                capture = await evidence_store.store_artifact(
                    source_path=Path(output_file),
                    original_filename=Path(output_file).name,
                    engagement_id=engagement_id,
                    job_id=job_id,
                    category="original",
                    format=fmt,
                    tool=adapter.tool_name,
                    tool_version=version,
                    interface=str(_interface) if isinstance(_interface, str) else None,
                    channel=int(_channel) if isinstance(_channel, int) else None,
                    bssid=str(_bssid) if isinstance(_bssid, str) else None,
                    ssid=str(_ssid) if isinstance(_ssid, str) else None,
                )

            # --- Actualizar resultado del job ---
            def _update_result() -> None:
                session = self._session_factory()
                try:
                    j = jobs_service.get_job(session, job_id)
                    j.result_summary = {
                        "tool": adapter.tool_name,
                        "tool_version": version,
                        **parsed,
                    }
                    if capture is not None:
                        j.result_summary["evidence_id"] = capture.id
                        j.result_summary["sha256"] = capture.sha256
                    session.commit()
                finally:
                    session.close()

            await asyncio.to_thread(_update_result)

            # --- WAITING_FOR_EVIDENCE → COMPLETED ---
            await self._transition(job_id, JobStatus.WAITING_FOR_EVIDENCE, "evidencia almacenada")
            await self._transition(
                job_id,
                JobStatus.COMPLETED,
                f"{adapter.tool_name} completado",
            )
            self._emit_event(
                job_id,
                engagement_id,
                "job_completed",
                {
                    "result": "ok",
                    "tool": adapter.tool_name,
                    "evidence_id": capture.id if capture else None,
                    "sha256": capture.sha256 if capture else None,
                    "parsed": parsed,
                },
            )

        except asyncio.CancelledError:
            await self._transition(job_id, JobStatus.CANCELLED, "trabajo cancelado por el operador")
            self._emit_event(
                job_id,
                engagement_id,
                "job_status_changed",
                {"status": JobStatus.CANCELLED.value},
            )
            if adapter is not None:
                await adapter.cleanup()
        except ToolNotInstalled as e:
            log.warning("tool not installed", job_id=job_id, tool=str(e))
            await self._transition(job_id, JobStatus.FAILED, message=str(e))
            self._emit_event(
                job_id,
                engagement_id,
                "job_failed",
                {"error": str(e)},
            )
        except Exception as e:
            log.error("job execution error", job_id=job_id, error=str(e), exc_info=True)
            await self._transition(job_id, JobStatus.FAILED, message=str(e))
            self._emit_event(
                job_id,
                engagement_id,
                "job_failed",
                {"error": str(e)},
            )

    # ------------------------------------------------------------------
    # Heartbeat loop
    # ------------------------------------------------------------------

    async def _heartbeat_loop(self) -> None:
        interval = self._config.heartbeat_interval
        while self._running:
            await asyncio.sleep(interval)

            def _check_stale() -> list[int]:
                session = self._session_factory()
                try:
                    stale = jobs_service.mark_stale_jobs(
                        session, heartbeat_timeout_seconds=interval * 2
                    )
                    return [j.id for j in stale]
                finally:
                    session.close()

            stale_ids = await asyncio.to_thread(_check_stale)
            for sid in stale_ids:
                self._emit_event(sid, 0, "job_failed", {"error": "heartbeat vencido"})
                task = self._active_jobs.pop(sid, None)
                if task is not None:
                    task.cancel()

    # ------------------------------------------------------------------
    # Recuperación tras reinicio
    # ------------------------------------------------------------------

    def _recover_pending_jobs(self) -> list[int]:
        """Busca trabajos no terminales al arrancar y los recoloca.

        QUEUED → se deja en QUEUED para ser re-encolado.
        PREPARING/RUNNING/PAUSED/CANCELLING → FAILED (no se puede restaurar el estado en Fase 1).
        """
        log = __import__("structlog").get_logger(__name__)
        session = self._session_factory()
        recovered: list[int] = []
        try:
            jobs = jobs_service.list_jobs(session, limit=1000)
            for j in jobs:
                status = JobStatus(j.status)
                if JobStateMachine.is_terminal(status):
                    continue
                if status == JobStatus.QUEUED:
                    recovered.append(j.id)
                    log.info("recovered queued job", job_id=j.id, kind=j.kind)
                else:
                    jobs_service.transition_job(
                        session,
                        j.id,
                        JobStatus.FAILED,
                        message="recuperación tras reinicio — trabajo no restaurable",
                    )
                    log.info("marked job as failed on recovery", job_id=j.id, status=j.status)
        finally:
            session.close()
        log.info(
            "recovery complete",
            recovered=len(recovered),
            total_checked=len(jobs) if "jobs" in dir() else 0,
        )
        return recovered

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _transition(
        self, job_id: int, status: JobStatus, message: str, *, started: bool = False
    ) -> None:
        def _do() -> int | None:
            session = self._session_factory()
            try:
                job_data: dict[str, object] = {"status": status}
                if started:
                    job_data["started_at"] = datetime.now(UTC)
                # mypy false positive: dynamic type noqa
                patch = type(
                    "_",
                    (),
                    {"model_dump": lambda self: job_data, "model_dump_json": lambda: ""},
                )()
                job = jobs_service.update_job(session, job_id, patch)
                return job.engagement_id
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()

        engagement_id = await asyncio.to_thread(_do)
        if engagement_id is not None:
            self._emit_event(
                job_id,
                engagement_id,
                "job_status_changed",
                {
                    "status": status.value,
                    "message": message,
                },
            )

    async def _update_progress(self, job_id: int, progress: float) -> None:
        def _do() -> None:
            session = self._session_factory()
            try:
                job = jobs_service.get_job(session, job_id)
                job.progress = progress
                session.commit()
            finally:
                session.close()

        await asyncio.to_thread(_do)

    def _emit_event(
        self, job_id: int, engagement_id: int, event_type: str, data: dict[str, object]
    ) -> None:
        envelope = JobEventEnvelope(
            event_type=event_type,
            job_id=job_id,
            engagement_id=engagement_id,
            data=data,
        )
        self._event_bus.publish(envelope)


# Singleton module-level accessor.

_manager_instance: JobManager | None = None


def get_job_manager() -> JobManager:
    """Devuelve la instancia singleton del JobManager."""
    if _manager_instance is None:
        raise RuntimeError("JobManager no ha sido inicializado — llamar desde lifespan")
    return _manager_instance


def set_job_manager(manager: JobManager) -> None:
    """Establece la instancia singleton (llamado desde lifespan)."""
    global _manager_instance  # noqa: PLW0603
    _manager_instance = manager


def reset_job_manager() -> None:
    """Reinicia el singleton (útil en tests)."""
    global _manager_instance  # noqa: PLW0603
    _manager_instance = None
