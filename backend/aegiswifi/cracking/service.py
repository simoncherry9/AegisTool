"""Servicio de orquestación de cracking (minuta §18).

Coordina la ejecución de planes multi-etapa de hashcat: crea y actualiza
registros en la base de datos, ejecuta cada etapa vía el adaptador,
monitorea progreso, y persiste resultados.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from aegiswifi.adapters.registry import get_adapter
from aegiswifi.core.config import get_settings
from aegiswifi.cracking.schemas import (
    AttackStage,
    CrackingPlan,
    CrackingProgress,
    CrackingResult,
    HashInfo,
)
from aegiswifi.database.engine import get_sessionmaker
from aegiswifi.database.models import (
    CrackingJob,
    CrackJobStatus,
    HandshakeArtifact,
    HandshakeQuality,
)
from aegiswifi.jobs.event_bus import EventBus, JobEventEnvelope


class CrackingService:
    """Orquestador de cracking de handshakes.

    Flujo típico::

        plan = planner.build_plan(...)
        result = await service.execute_plan(plan)
    """

    def __init__(
        self,
        event_bus: EventBus | None = None,
    ) -> None:
        self._bus = event_bus or EventBus()
        self._active_jobs: dict[int, CrackingProgress] = {}

    # ------------------------------------------------------------------
    # Validación de handshakes
    # ------------------------------------------------------------------

    def validate_artifact(self, artifact: HandshakeArtifact) -> None:
        """Valida que un handshake sea apto para cracking.

        Raises:
            ValueError: Si el handshake no está validado o su calidad es
                insuficiente.
        """
        if not artifact.validated:
            raise ValueError(f"HandshakeArtifact #{artifact.id} no está validado")
        if artifact.quality in (HandshakeQuality.INVALID, HandshakeQuality.POOR):
            raise ValueError(
                f"HandshakeArtifact #{artifact.id} tiene calidad "
                f"{artifact.quality}, se requiere ≥ ACCEPTABLE"
            )
        if not artifact.hash22000_path:
            raise ValueError(f"HandshakeArtifact #{artifact.id} no tiene archivo .22000")

    # ------------------------------------------------------------------
    # Ejecución de plan
    # ------------------------------------------------------------------

    async def execute_plan(
        self,
        plan: CrackingPlan,
        engagement_id: int,
        session: Session | None = None,
    ) -> CrackingResult:
        """Ejecuta un plan multi-etapa completo.

        Cada etapa se ejecuta secuencialmente. Si una etapa recupera la
        contraseña, las restantes se omiten.

        Args:
            plan: Plan de cracking a ejecutar.
            engagement_id: ID del engagement asociado.
            session: Sesión de BD (opcional; si no se provee, se crea una).

        Returns:
            :class:`CrackingResult` con el resultado de la ejecución.
        """
        own_session = session is None
        if own_session:
            SessionLocal = get_sessionmaker()
            session = SessionLocal()

        assert session is not None

        try:
            return await self._execute_with_session(plan, engagement_id, session)
        finally:
            if own_session:
                session.close()

    async def _execute_with_session(
        self,
        plan: CrackingPlan,
        engagement_id: int,
        session: Session,
    ) -> CrackingResult:
        """Ejecuta el plan con una sesión de BD ya abierta."""
        from aegiswifi.core.security import encrypt_secret

        # Crear/actualizar CrackingJob.
        job = self._init_job(session, plan, engagement_id)

        result = CrackingResult(
            job_id=job.id,
            stages_total=len(plan.stages),
        )

        config = get_settings().jobs

        for idx, stage in enumerate(plan.stages):
            # Actualizar estado.
            self._transition_job(session, job.id, CrackJobStatus.RUNNING)

            # Crear adaptador para esta etapa.
            adapter = get_adapter(
                "password_audit",
                job_id=job.id,
                engagement_id=engagement_id,
                event_bus=self._bus,
                config=config,
            )

            # Construir opciones para esta etapa.
            options = self._stage_to_options(stage, plan.hash_file_path, plan.hash_mode)

            # Ejecutar.
            try:
                adapter_result = await adapter.start({"options": options})
                collected = await adapter.collect_results()
            except Exception:
                self._transition_job(session, job.id, CrackJobStatus.FAILED)
                result.exit_code = -1
                return result

            result.stages_executed = idx + 1
            result.exit_code = collected.get("exit_code")
            result.peak_speed = max(result.peak_speed, collected.get("peak_speed", 0))

            # ¿Password recuperado?
            if collected.get("cracked") and collected.get("password"):
                password = collected["password"]
                encrypted = encrypt_secret(password)
                result.cracked = True
                result.password = password
                result.encrypted_secret = encrypted
                result.mode_used = stage.mode

                # Actualizar BD.
                job.recovered = True
                job.encrypted_secret = encrypted
                job.finished_at = datetime.now(UTC)
                self._transition_job(session, job.id, CrackJobStatus.RECOVERED)
                session.commit()

                self._emit_event(
                    "cracking_recovered",
                    job.id,
                    engagement_id,
                    {"mode": stage.mode.value, "stages_used": idx + 1},
                )
                return result

            # Actualizar progreso.
            job.progress = 1.0  # esta etapa está agotada
            job.speed = collected.get("peak_speed", 0)
            session.commit()

        # Todas las etapas agotadas.
        job.finished_at = datetime.now(UTC)
        self._transition_job(session, job.id, CrackJobStatus.EXHAUSTED)
        session.commit()

        self._emit_event(
            "cracking_exhausted",
            job.id,
            engagement_id,
            {"stages_executed": len(plan.stages)},
        )
        return result

    # ------------------------------------------------------------------
    # Operaciones con CrackingJob
    # ------------------------------------------------------------------

    def create_cracking_job(
        self,
        session: Session,
        artifact_id: int,
        strategy: str = "dictionary",
        engagement_id: int | None = None,
    ) -> CrackingJob:
        """Crea un nuevo CrackingJob en la base de datos."""
        job = CrackingJob(
            artifact_id=artifact_id,
            strategy=strategy,
            status=CrackJobStatus.CREATED,
        )
        session.add(job)
        session.commit()
        session.refresh(job)

        self._emit_event(
            "cracking_created",
            job.id,
            engagement_id or 0,
            {"artifact_id": artifact_id, "strategy": strategy},
        )
        return job

    def get_job(self, session: Session, job_id: int) -> CrackingJob | None:
        """Obtiene un CrackingJob por ID."""
        return session.get(CrackingJob, job_id)

    def list_jobs(
        self,
        session: Session,
        engagement_id: int | None = None,
        status: str | None = None,
    ) -> list[CrackingJob]:
        """Lista CrackingJobs, opcionalmente filtrados."""
        stmt = select(CrackingJob)
        if engagement_id is not None:
            stmt = (
                stmt.join(HandshakeArtifact, CrackingJob.artifact_id == HandshakeArtifact.id)
                .join(HandshakeArtifact.capture)
                .where(HandshakeArtifact.capture.has(engagement_id=engagement_id))
            )
        if status:
            stmt = stmt.where(CrackingJob.status == status)
        return list(session.scalars(stmt.order_by(CrackingJob.id)).all())

    def cancel_job(self, session: Session, job_id: int) -> CrackingJob | None:
        """Cancela un CrackingJob pendiente o en ejecución."""
        job = session.get(CrackingJob, job_id)
        if job is None:
            return None
        if job.status in (CrackJobStatus.RUNNING, CrackJobStatus.QUEUED, CrackJobStatus.CREATED):
            job.status = CrackJobStatus.CANCELLED
            job.finished_at = datetime.now(UTC)
            session.commit()
        return job

    # ------------------------------------------------------------------
    # HashInfo
    # ------------------------------------------------------------------

    def get_hash_info(
        self,
        artifact: HandshakeArtifact,
    ) -> HashInfo | None:
        """Extrae información del archivo .22000 asociado a un artifact."""
        if not artifact.hash22000_path:
            return None

        path = artifact.hash22000_path
        try:
            with open(path) as f:
                first_line = f.readline().strip()
        except (OSError, FileNotFoundError):
            return None

        # Formato 22000: hash:hash:essid:bssid:...
        # Formato 22000: el separador de campos es * (no :), aunque
        # algunos archivos usan : entre valores.
        # Intentamos parseo flexible.
        bssid: str | None = None
        ssid: str | None = None
        if "*" in first_line:
            fields = first_line.split("*")
            # Formato típico: WPA*01*...*bssid*station*essid*...
            if len(fields) >= 6:
                bssid = fields[3] if fields[3] else None
                ssid = fields[5] if fields[5] else None
        else:
            parts = first_line.split(":")
            if len(parts) > 3:
                ssid = parts[2]
                # BSSID puede contener :, así que reconstruimos desde parts[3:5]
                bssid_candidates = parts[3:]
                if bssid_candidates:
                    bssid = ":".join(bssid_candidates[:6])  # máx 6 pares hex
        return HashInfo(
            artifact_id=artifact.id,
            hash_file_path=path,
            hash_line=first_line[:80],
            bssid=bssid,
            ssid=ssid,
            kind="pmkid" if "pmkid" in artifact.kind else "eapol",
        )

    # ------------------------------------------------------------------
    # Internos
    # ------------------------------------------------------------------

    def _init_job(
        self,
        session: Session,
        plan: CrackingPlan,
        engagement_id: int,
    ) -> CrackingJob:
        """Inicializa o recupera el CrackingJob en BD."""
        job = session.get(CrackingJob, plan.job_id)
        if job is None:
            job = CrackingJob(
                id=plan.job_id,
                artifact_id=plan.artifact_id,
                strategy=f"multi_stage_{len(plan.stages)}_steps",
                status=CrackJobStatus.CREATED,
            )
            session.add(job)
            session.commit()
            session.refresh(job)

        job.status = CrackJobStatus.VALIDATING
        job.started_at = datetime.now(UTC)
        session.commit()
        return job

    @staticmethod
    def _transition_job(
        session: Session,
        job_id: int,
        new_status: CrackJobStatus,
    ) -> None:
        """Transiciona el estado de un CrackingJob."""
        job = session.get(CrackingJob, job_id)
        if job is not None:
            job.status = new_status.value

    @staticmethod
    def _stage_to_options(
        stage: AttackStage,
        hash_file_path: str,
        hash_mode: int,
    ) -> dict[str, Any]:
        """Convierte un AttackStage a dict de opciones para el adaptador."""
        options: dict[str, Any] = {
            "hash_file": hash_file_path,
            "hash_mode": hash_mode,
            "attack_mode": stage.mode,
        }

        if stage.dictionary_path:
            options["dictionary"] = stage.dictionary_path
        if stage.rules_path:
            options["rules"] = stage.rules_path
        if stage.mask:
            options["mask"] = stage.mask
        if stage.custom_charset_1:
            options["custom_charset_1"] = stage.custom_charset_1
        if stage.custom_charset_2:
            options["custom_charset_2"] = stage.custom_charset_2
        if stage.extra_args:
            options["extra_args"] = stage.extra_args

        return options

    def _emit_event(
        self,
        event_type: str,
        job_id: int,
        engagement_id: int,
        data: dict[str, Any],
    ) -> None:
        """Publica un evento en el EventBus."""
        envelope = JobEventEnvelope(
            event_type=event_type,
            job_id=job_id,
            engagement_id=engagement_id,
            timestamp=datetime.now(UTC).isoformat(),
            data=data,
        )
        self._bus.publish(envelope)


# Singleton.
_cracking_service: CrackingService | None = None


def get_cracking_service(event_bus: EventBus | None = None) -> CrackingService:
    """Retorna el singleton del servicio de cracking."""
    global _cracking_service
    if _cracking_service is None:
        _cracking_service = CrackingService(event_bus=event_bus)
    return _cracking_service
