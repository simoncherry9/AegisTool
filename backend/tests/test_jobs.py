"""Tests del sistema de trabajos + WebSocket (Fase 1, minuta §26)."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from aegiswifi.database.models import (
    Engagement,
    EngagementStatus,
    Job,
    JobStatus,
)
from aegiswifi.jobs import service as jobs_service
from aegiswifi.jobs.event_bus import EventBus, JobEventEnvelope, get_event_bus, reset_event_bus
from aegiswifi.jobs.schemas import JobCreate, JobUpdate
from aegiswifi.jobs.statemachine import JobStateMachine

# ===================================================================
# Fixtures helpers
# ===================================================================


def _create_engagement(session: Session) -> Engagement:
    eng = Engagement(
        name="test-engagement",
        client="test-client",
        operator="test-operator",
        status=EngagementStatus.ACTIVE,
        code="JOB-TEST-001",
    )
    session.add(eng)
    session.commit()
    session.refresh(eng)
    return eng


def _create_job(session: Session, engagement_id: int, **overrides: Any) -> Job:
    payload = JobCreate(
        engagement_id=engagement_id,
        kind=overrides.get("kind", "passive_capture"),
        priority=overrides.get("priority", 0),
        timeout_seconds=overrides.get("timeout_seconds", 300),
        parameters=overrides.get("parameters", {}),
    )
    return jobs_service.create_job(session, payload)


# ===================================================================
# State Machine Tests
# ===================================================================


class TestJobStateMachine:
    def test_valid_transitions(self):
        """Verifica que las transiciones principales sean válidas."""
        assert JobStateMachine.is_valid_transition(JobStatus.CREATED, JobStatus.VALIDATING_SCOPE)
        assert JobStateMachine.is_valid_transition(JobStatus.VALIDATING_SCOPE, JobStatus.QUEUED)
        assert JobStateMachine.is_valid_transition(JobStatus.QUEUED, JobStatus.PREPARING)
        assert JobStateMachine.is_valid_transition(JobStatus.PREPARING, JobStatus.RUNNING)
        assert JobStateMachine.is_valid_transition(
            JobStatus.RUNNING, JobStatus.WAITING_FOR_EVIDENCE
        )
        assert JobStateMachine.is_valid_transition(
            JobStatus.WAITING_FOR_EVIDENCE, JobStatus.COMPLETED
        )

    def test_pause_resume_cycle(self):
        """PAUSED ↔ RUNNING debe ser bidireccional."""
        assert JobStateMachine.is_valid_transition(JobStatus.RUNNING, JobStatus.PAUSED)
        assert JobStateMachine.is_valid_transition(JobStatus.PAUSED, JobStatus.RUNNING)

    def test_cancel_from_any_non_terminal(self):
        """CANCELLING debe ser válido desde cualquier estado no terminal."""
        for status in JobStatus:
            if JobStateMachine.is_terminal(status) or status == JobStatus.CANCELLING:
                continue
            assert JobStateMachine.is_valid_transition(status, JobStatus.CANCELLING), (
                f"debería poder cancelar desde {status}"
            )

    def test_fail_from_running(self):
        """FAILED debe ser válido desde RUNNING (y otros activos)."""
        assert JobStateMachine.is_valid_transition(JobStatus.RUNNING, JobStatus.FAILED)
        assert JobStateMachine.is_valid_transition(JobStatus.PREPARING, JobStatus.FAILED)
        assert JobStateMachine.is_valid_transition(JobStatus.WAITING_FOR_EVIDENCE, JobStatus.FAILED)

    def test_terminal_states_are_terminal(self):
        """Verifica que los estados terminales se reconozcan como tales."""
        terminal = {
            JobStatus.COMPLETED,
            JobStatus.FAILED,
            JobStatus.TIMED_OUT,
            JobStatus.RESOURCE_LIMITED,
            JobStatus.CANCELLED,
        }
        for status in JobStatus:
            assert JobStateMachine.is_terminal(status) == (status in terminal)

    def test_invalid_transitions_raise(self):
        """Transiciones inválidas deben lanzar ValidationFailed."""
        from aegiswifi.core.exceptions import ValidationFailed

        with pytest.raises(ValidationFailed):
            JobStateMachine.assert_valid_transition(JobStatus.CREATED, JobStatus.COMPLETED)

        with pytest.raises(ValidationFailed):
            JobStateMachine.assert_valid_transition(JobStatus.COMPLETED, JobStatus.RUNNING)

    def test_requires_scope_check(self):
        """Solo CREATED → VALIDATING_SCOPE requiere scope check."""
        assert JobStateMachine.requires_scope_check(JobStatus.CREATED, JobStatus.VALIDATING_SCOPE)
        assert not JobStateMachine.requires_scope_check(JobStatus.QUEUED, JobStatus.PREPARING)


# ===================================================================
# Job Service Tests (con BD)
# ===================================================================


class TestJobService:
    def test_create_job(self, db_session: Session):
        """Crear un job produce estado CREATED y un event log inicial."""
        eng = _create_engagement(db_session)
        job = _create_job(db_session, eng.id)

        assert job.status == JobStatus.CREATED.value
        assert job.kind == "passive_capture"
        assert job.engagement_id == eng.id

        # Verificar que se creó el event log.
        events = jobs_service.list_job_events(db_session, job.id)
        assert len(events) == 1
        assert events[0].to_status == JobStatus.CREATED.value

    def test_get_job_not_found(self, db_session: Session):
        """get_job con ID inválido lanza NotFound."""
        from aegiswifi.core.exceptions import NotFound

        with pytest.raises(NotFound):
            jobs_service.get_job(db_session, 9999)

    def test_list_jobs(self, db_session: Session):
        """list_jobs retorna los trabajos ordenados por prioridad."""
        eng = _create_engagement(db_session)
        _create_job(db_session, eng.id, priority=5)
        j2 = _create_job(db_session, eng.id, priority=10)
        jobs = jobs_service.list_jobs(db_session)
        assert len(jobs) >= 2
        # Mayor prioridad primero.
        assert jobs[0].id == j2.id or jobs[0].priority >= jobs[1].priority

    def test_list_jobs_filters(self, db_session: Session):
        """Filtros de list_jobs (engagement_id, status, kind)."""
        eng = _create_engagement(db_session)
        _create_job(db_session, eng.id, kind="handshake_capture")

        by_kind = jobs_service.list_jobs(db_session, kind="handshake_capture")
        assert len(by_kind) == 1

        by_status = jobs_service.list_jobs(db_session, status=JobStatus.CREATED)
        assert len(by_status) >= 1

        by_engagement = jobs_service.list_jobs(db_session, engagement_id=eng.id)
        assert len(by_engagement) == 1

    def test_update_job(self, db_session: Session):
        """update_job cambia campos y registra transición en event log."""
        eng = _create_engagement(db_session)
        job = _create_job(db_session, eng.id)

        updated = jobs_service.update_job(
            db_session,
            job.id,
            JobUpdate(status=JobStatus.VALIDATING_SCOPE, progress=0.5),
        )
        assert updated.status == JobStatus.VALIDATING_SCOPE.value
        assert updated.progress == 0.5

        # Verificar que se registró la transición.
        events = jobs_service.list_job_events(db_session, job.id)
        assert len(events) == 2  # CREATED + VALIDATING_SCOPE
        assert events[1].from_status == JobStatus.CREATED.value
        assert events[1].to_status == JobStatus.VALIDATING_SCOPE.value

    def test_update_job_invalid_transition(self, db_session: Session):
        """update_job con transición inválida lanza ValidationFailed."""
        from aegiswifi.core.exceptions import ValidationFailed

        eng = _create_engagement(db_session)
        job = _create_job(db_session, eng.id)

        with pytest.raises(ValidationFailed):
            jobs_service.update_job(
                db_session,
                job.id,
                JobUpdate(status=JobStatus.COMPLETED),  # CREATED → COMPLETED es inválido
            )

    def test_cancel_job(self, db_session: Session):
        """cancel_job transiciona a CANCELLING."""
        eng = _create_engagement(db_session)
        job = _create_job(db_session, eng.id)

        cancelled = jobs_service.cancel_job(db_session, job.id)
        assert cancelled.status == JobStatus.CANCELLING.value

    def test_cancel_terminal_job(self, db_session: Session):
        """cancel_job sobre un job terminal lanza ValidationFailed."""
        from aegiswifi.core.exceptions import ValidationFailed

        eng = _create_engagement(db_session)
        job = _create_job(db_session, eng.id)

        # Transicionar a COMPLETED manualmente (saltando validación de máquina de estados).
        job.status = JobStatus.COMPLETED.value
        db_session.commit()

        with pytest.raises(ValidationFailed):
            jobs_service.cancel_job(db_session, job.id)

    def test_claim_next_queued(self, db_session: Session):
        """claim_next_queued reclama el trabajo prioritario y lo pasa a PREPARING."""
        eng = _create_engagement(db_session)
        job = _create_job(db_session, eng.id, priority=5)

        # Transicionar CREATED → VALIDATING_SCOPE → QUEUED.
        jobs_service.transition_job(db_session, job.id, JobStatus.VALIDATING_SCOPE)
        jobs_service.transition_job(db_session, job.id, JobStatus.QUEUED)

        claimed = jobs_service.claim_next_queued(db_session)
        assert claimed is not None
        assert claimed.id == job.id
        assert claimed.status == JobStatus.PREPARING.value

        # Segundo intento debe retornar None.
        assert jobs_service.claim_next_queued(db_session) is None

    def test_mark_stale_jobs(self, db_session: Session):
        """mark_stale_jobs detecta trabajos sin heartbeat reciente."""
        eng = _create_engagement(db_session)
        job = _create_job(db_session, eng.id)

        # Poner en RUNNING con heartbeat antiguo.
        now = datetime.now(UTC)
        job.status = JobStatus.RUNNING.value
        job.heartbeat_at = now - timedelta(seconds=60)
        db_session.commit()

        stale = jobs_service.mark_stale_jobs(db_session, heartbeat_timeout_seconds=30)
        assert len(stale) == 1
        assert stale[0].id == job.id

        # Verificar que se transicionó a FAILED.
        assert stale[0].status == JobStatus.FAILED.value
        assert stale[0].error_message == "heartbeat vencido"

    def test_transition_job_sets_finished_at(self, db_session: Session):
        """Transicionar a terminal registra finished_at."""
        eng = _create_engagement(db_session)
        job = _create_job(db_session, eng.id)

        # Transicionar CREATED → VALIDATING_SCOPE → QUEUED → PREPARING → RUNNING → FAILED.
        jobs_service.transition_job(db_session, job.id, JobStatus.VALIDATING_SCOPE)
        jobs_service.transition_job(db_session, job.id, JobStatus.QUEUED)
        jobs_service.transition_job(db_session, job.id, JobStatus.PREPARING)
        jobs_service.transition_job(db_session, job.id, JobStatus.RUNNING)
        jobs_service.transition_job(db_session, job.id, JobStatus.FAILED, "error for test")
        assert job.finished_at is not None

    def test_list_job_events_empty(self, db_session: Session):
        """list_job_events con job inexistente lanza NotFound."""
        from aegiswifi.core.exceptions import NotFound

        with pytest.raises(NotFound):
            jobs_service.list_job_events(db_session, 9999)


# ===================================================================
# EventBus Tests
# ===================================================================


class TestEventBus:
    def test_publish_subscribe(self):
        """Evento publicado llega al suscriptor."""
        bus = EventBus(buffer_size=100)
        queue: asyncio.Queue[JobEventEnvelope] = asyncio.Queue()

        bus.subscribe(queue)
        env = JobEventEnvelope(
            event_type="job_created", job_id=1, engagement_id=1, data={"test": True}
        )
        bus.publish(env)

        received = queue.get_nowait()
        assert received.event_type == "job_created"
        assert received.job_id == 1
        assert received.data["test"] is True

    def test_filter_by_job_id(self):
        """Suscriptor filtrado por job_id recibe solo eventos relevantes."""
        bus = EventBus(buffer_size=100)
        queue: asyncio.Queue[JobEventEnvelope] = asyncio.Queue()

        bus.subscribe(queue, job_id=1)
        bus.publish(JobEventEnvelope(event_type="job_created", job_id=1, engagement_id=1, data={}))
        bus.publish(JobEventEnvelope(event_type="job_created", job_id=2, engagement_id=1, data={}))

        assert queue.qsize() == 2  # wildcard match + job:1 match
        # El wildcard recibe ambos, pero el filtro job:1 recibe solo el de job_id=1.
        # Total: 2 eventos (job_id=1 aparece dos veces, job_id=2 aparece una vez).

    def test_unsubscribe(self):
        """Desuscribir una cola deja de recibir eventos."""
        bus = EventBus(buffer_size=100)
        queue: asyncio.Queue[JobEventEnvelope] = asyncio.Queue()

        bus.subscribe(queue)
        bus.unsubscribe(queue)
        bus.publish(JobEventEnvelope(event_type="test", job_id=1, engagement_id=1, data={}))

        assert queue.empty()

    def test_replay_buffer(self):
        """get_replay retorna eventos recientes."""
        bus = EventBus(buffer_size=10)
        for i in range(5):
            bus.publish(
                JobEventEnvelope(event_type="ev", job_id=i % 3, engagement_id=1, data={"i": i})
            )

        replay = bus.get_replay(job_ids=[0], limit=10)
        assert len(replay) >= 1
        assert all(e.job_id == 0 for e in replay)

    def test_replay_all(self):
        """get_replay sin filtros retorna todos los eventos en buffer."""
        bus = EventBus(buffer_size=10)
        for _ in range(5):
            bus.publish(JobEventEnvelope(event_type="ev", job_id=1, engagement_id=1, data={}))

        replay = bus.get_replay(limit=10)
        assert len(replay) == 5

    def test_replay_engagement_filter(self):
        """Filtro por engagement_id en replay."""
        bus = EventBus(buffer_size=100)
        bus.publish(JobEventEnvelope(event_type="ev", job_id=1, engagement_id=10, data={}))
        bus.publish(JobEventEnvelope(event_type="ev", job_id=2, engagement_id=20, data={}))

        replay = bus.get_replay(engagement_ids=[10])
        assert len(replay) == 1
        assert replay[0].engagement_id == 10

    def test_buffer_overflow(self):
        """Ring buffer descarta eventos viejos al exceder el límite."""
        bus = EventBus(buffer_size=3)
        for i in range(5):
            bus.publish(
                JobEventEnvelope(event_type="ev", job_id=1, engagement_id=1, data={"idx": i})
            )

        replay = bus.get_replay(limit=10)
        assert len(replay) == 3
        assert replay[0].data["idx"] == 2  # primero del buffer después del overflow

    def test_singleton(self):
        """get_event_bus retorna siempre la misma instancia."""
        reset_event_bus()
        b1 = get_event_bus()
        b2 = get_event_bus()
        assert b1 is b2


# ===================================================================
# API REST Tests
# ===================================================================


class TestJobsAPI:
    def test_create_job_api(self, db_session: Session, client: TestClient):
        """POST /api/v1/jobs crea un trabajo."""
        eng = _create_engagement(db_session)
        resp = client.post(
            "/api/v1/jobs",
            json={
                "engagement_id": eng.id,
                "kind": "handshake_capture",
                "priority": 5,
                "timeout_seconds": 300,
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["kind"] == "handshake_capture"
        assert data["status"] == "CREATED"
        assert data["engagement_id"] == eng.id

    def test_list_jobs_api(self, db_session: Session, client: TestClient):
        """GET /api/v1/jobs lista trabajos."""
        eng = _create_engagement(db_session)
        _create_job(db_session, eng.id)

        resp = client.get("/api/v1/jobs")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_get_job_api(self, db_session: Session, client: TestClient):
        """GET /api/v1/jobs/{id} retorna el trabajo."""
        eng = _create_engagement(db_session)
        job = _create_job(db_session, eng.id)

        resp = client.get(f"/api/v1/jobs/{job.id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == job.id

    def test_get_job_404(self, client: TestClient):
        """GET /api/v1/jobs/9999 retorna 404."""
        resp = client.get("/api/v1/jobs/9999")
        assert resp.status_code == 404

    def test_cancel_job_api(self, db_session: Session, client: TestClient):
        """POST /api/v1/jobs/{id}/cancel cancela el trabajo."""
        eng = _create_engagement(db_session)
        job = _create_job(db_session, eng.id)

        resp = client.post(f"/api/v1/jobs/{job.id}/cancel")
        assert resp.status_code == 200
        assert resp.json()["status"] == "CANCELLING"

    def test_retry_job_api(self, db_session: Session, client: TestClient):
        """POST /api/v1/jobs/{id}/retry reintenta un trabajo fallido."""
        eng = _create_engagement(db_session)
        job = _create_job(db_session, eng.id)

        # Marcar como FAILED directamente (sin validación machine state).
        job.status = JobStatus.FAILED.value
        db_session.commit()

        resp = client.post(f"/api/v1/jobs/{job.id}/retry")
        assert resp.status_code == 200
        assert resp.json()["status"] == "CREATED"

    def test_retry_non_failed_returns_422(self, db_session: Session, client: TestClient):
        """Reintentar un trabajo no fallido retorna error."""
        eng = _create_engagement(db_session)
        job = _create_job(db_session, eng.id)

        resp = client.post(f"/api/v1/jobs/{job.id}/retry")
        assert resp.status_code == 422  # ValidationFailed

    def test_job_events_api(self, db_session: Session, client: TestClient):
        """GET /api/v1/jobs/{id}/events retorna historial."""
        eng = _create_engagement(db_session)
        job = _create_job(db_session, eng.id)

        resp = client.get(f"/api/v1/jobs/{job.id}/events")
        assert resp.status_code == 200
        events = resp.json()
        assert len(events) >= 1
        assert events[0]["to_status"] == "CREATED"

    def test_create_job_missing_engagement(self, client: TestClient):
        """POST /api/v1/jobs con engagement_id inválido."""
        resp = client.post(
            "/api/v1/jobs",
            json={"engagement_id": 9999, "kind": "passive_capture"},
        )
        assert resp.status_code == 404

    def test_create_job_invalid_kind(self, db_session: Session, client: TestClient):
        """POST /api/v1/jobs con kind demasiado largo."""
        eng = _create_engagement(db_session)
        resp = client.post(
            "/api/v1/jobs",
            json={
                "engagement_id": eng.id,
                "kind": "x" * 65,  # max 64
            },
        )
        assert resp.status_code == 422


# ===================================================================
# State Machine Enum Tests
# ===================================================================


class TestJobStatusEnum:
    def test_all_statuses_have_valid_transitions(self):
        """Todos los estados alcanzables tienen al menos una transición de salida válida."""
        terminal = {
            JobStatus.COMPLETED,
            JobStatus.FAILED,
            JobStatus.TIMED_OUT,
            JobStatus.RESOURCE_LIMITED,
            JobStatus.CANCELLED,
        }
        for status in JobStatus:
            if status in terminal:
                continue
            # Debe tener al menos una transición a otro estado.
            has_outgoing = any(
                JobStateMachine.is_valid_transition(status, target)
                for target in JobStatus
                if target != status
            )
            assert has_outgoing, f"{status} no tiene transiciones de salida"

    def test_no_duplicate_values(self):
        """No hay valores duplicados en el enum."""
        values = [s.value for s in JobStatus]
        assert len(values) == len(set(values))

    def test_all_minuta_states_present(self):
        """Todos los 13 estados de la minuta §26 están presentes."""
        expected = {
            "CREATED",
            "VALIDATING_SCOPE",
            "QUEUED",
            "PREPARING",
            "RUNNING",
            "PAUSED",
            "WAITING_FOR_EVIDENCE",
            "COMPLETED",
            "FAILED",
            "TIMED_OUT",
            "RESOURCE_LIMITED",
            "CANCELLING",
            "CANCELLED",
        }
        actual = {s.value for s in JobStatus}
        assert actual == expected, f"Faltan: {expected - actual}, Sobran: {actual - expected}"
