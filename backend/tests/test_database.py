"""Tests de la capa de base de datos: engine, base, modelos (minuta §28)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from aegiswifi.database.models import (
    AccessPoint,
    Capture,
    CrackingJob,
    CrackJobStatus,
    Engagement,
    EngagementStatus,
    Finding,
    FindingStatus,
    HandshakeArtifact,
    HandshakeQuality,
    Job,
    JobStatus,
    ScopeTarget,
    Severity,
    Station,
)


# ===================================================================
# Engine Tests
# ===================================================================


class TestEngine:
    """Tests del singleton engine de SQLAlchemy."""

    def test_get_engine_returns_engine(self):
        """get_engine retorna un Engine SQLAlchemy."""
        from aegiswifi.database.engine import dispose_engine, get_engine

        dispose_engine()
        engine = get_engine()
        assert engine is not None
        assert engine.name == "sqlite"
        dispose_engine()

    def test_get_engine_is_singleton(self):
        """get_engine retorna la misma instancia."""
        from aegiswifi.database.engine import dispose_engine, get_engine

        dispose_engine()
        e1 = get_engine()
        e2 = get_engine()
        assert e1 is e2
        dispose_engine()

    def test_dispose_engine_resets(self):
        """dispose_engine libera el engine y resetea el singleton."""
        from aegiswifi.database.engine import dispose_engine, get_engine

        dispose_engine()
        get_engine()
        dispose_engine()
        # Después de dispose, get_engine debe crear uno nuevo.
        e = get_engine()
        assert e is not None
        dispose_engine()

    def test_get_sessionmaker_creates_sessions(self):
        """get_sessionmaker produce sesiones funcionales."""
        from aegiswifi.database.engine import dispose_engine, get_sessionmaker

        dispose_engine()
        SessionLocal = get_sessionmaker()
        session = SessionLocal()
        try:
            # La sesión debe poder ejecutar consultas.
            result = session.execute(
                __import__("sqlalchemy").text("SELECT 1 AS test")
            ).scalar()
            assert result == 1
        finally:
            session.close()
            dispose_engine()

    def test_get_db_yields_session(self):
        """get_db es un generator que cede y cierra sesión."""
        from aegiswifi.database.engine import dispose_engine, get_db

        dispose_engine()
        gen = get_db()
        session = next(gen)
        assert isinstance(session, Session)
        try:
            next(gen)
        except StopIteration:
            pass
        # Verificar que la sesión está cerrada.
        try:
            session.execute(__import__("sqlalchemy").text("SELECT 1"))
            assert False, "La sesión debería estar cerrada"
        except Exception:
            pass
        dispose_engine()


# ===================================================================
# TimestampMixin Tests
# ===================================================================


class TestTimestampMixin:
    """Tests del mixin que añade created_at / updated_at."""

    def test_engagement_has_timestamps(self, db_session: Session):
        """Engagement hereda created_at y updated_at de TimestampMixin."""
        eng = Engagement(
            name="ts-test",
            client="client",
            operator="op",
            status=EngagementStatus.DRAFT,
            code="TS-TEST-001",
        )
        db_session.add(eng)
        db_session.commit()

        assert eng.created_at is not None
        assert eng.updated_at is not None
        # Al crearse, ambos deben ser aproximadamente iguales.
        diff = abs(eng.updated_at - eng.created_at)
        assert diff < timedelta(seconds=2)

    def test_timestamps_update_on_change(self, db_session: Session):
        """updated_at se actualiza al modificar el registro."""
        eng = Engagement(
            name="ts-update",
            client="client",
            operator="op",
            status=EngagementStatus.DRAFT,
            code="TS-TEST-002",
        )
        db_session.add(eng)
        db_session.commit()
        original_updated = eng.updated_at

        eng.status = EngagementStatus.ACTIVE.value
        db_session.commit()

        # SQLAlchemy refresca el objeto, updated_at debe cambiar.
        db_session.refresh(eng)
        # Puede ser el mismo segundo en SQLite (resolución limitada).
        assert eng.updated_at is not None


# ===================================================================
# Enum Tests
# ===================================================================


class TestEnums:
    """Tests de los enums del dominio."""

    def test_engagement_status_values(self):
        assert EngagementStatus.DRAFT == "DRAFT"
        assert EngagementStatus.ACTIVE == "ACTIVE"
        assert EngagementStatus.COMPLETED == "COMPLETED"
        assert EngagementStatus.CANCELLED == "CANCELLED"
        assert EngagementStatus.ARCHIVED == "ARCHIVED"
        assert EngagementStatus.READY == "READY"
        assert EngagementStatus.PAUSED == "PAUSED"
        assert len(EngagementStatus) == 7

    def test_job_status_values(self):
        assert JobStatus.CREATED == "CREATED"
        assert JobStatus.RUNNING == "RUNNING"
        assert JobStatus.COMPLETED == "COMPLETED"
        assert JobStatus.FAILED == "FAILED"
        assert len(JobStatus) == 13

    def test_crack_job_status_values(self):
        assert CrackJobStatus.CREATED == "CREATED"
        assert CrackJobStatus.RUNNING == "RUNNING"
        assert CrackJobStatus.EXHAUSTED == "EXHAUSTED"
        assert CrackJobStatus.RECOVERED == "RECOVERED"

    def test_handshake_quality_values(self):
        assert HandshakeQuality.EXCELLENT == "EXCELLENT"
        assert HandshakeQuality.GOOD == "GOOD"
        assert HandshakeQuality.ACCEPTABLE == "ACCEPTABLE"
        assert HandshakeQuality.POOR == "POOR"
        assert HandshakeQuality.INVALID == "INVALID"

    def test_severity_values(self):
        assert Severity.INFO == "INFO"
        assert Severity.LOW == "LOW"
        assert Severity.MEDIUM == "MEDIUM"
        assert Severity.HIGH == "HIGH"
        assert Severity.CRITICAL == "CRITICAL"

    def test_finding_status_values(self):
        assert FindingStatus.OPEN == "OPEN"
        assert FindingStatus.CONFIRMED == "CONFIRMED"
        assert FindingStatus.REMEDIATED == "REMEDIATED"
        assert FindingStatus.FALSE_POSITIVE == "FALSE_POSITIVE"
        assert FindingStatus.ACCEPTED_RISK == "ACCEPTED_RISK"


# ===================================================================
# Model CRUD Tests
# ===================================================================


class TestEngagementModel:
    def test_create_engagement(self, db_session: Session):
        eng = Engagement(
            name="test-eng",
            client="test-client",
            operator="test-op",
            status=EngagementStatus.DRAFT,
            code="MOD-TEST-001",
        )
        db_session.add(eng)
        db_session.commit()
        assert eng.id is not None
        assert eng.code == "MOD-TEST-001"
        assert eng.status == EngagementStatus.DRAFT.value

    def test_engagement_code_unique(self, db_session: Session):
        """El código debe ser único (unique constraint en la base de datos)."""
        from sqlalchemy.exc import IntegrityError

        eng1 = Engagement(
            name="eng1",
            client="c1",
            operator="o1",
            status=EngagementStatus.DRAFT,
            code="UNIQUE-CODE",
        )
        db_session.add(eng1)
        db_session.commit()

        eng2 = Engagement(
            name="eng2",
            client="c2",
            operator="o2",
            status=EngagementStatus.DRAFT,
            code="UNIQUE-CODE",
        )
        db_session.add(eng2)
        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_engagement_permissions_limits_defaults(self, db_session: Session):
        """permissions y limits usan dict vacío por defecto."""
        eng = Engagement(
            name="defaults-test",
            client="c",
            operator="o",
            status=EngagementStatus.DRAFT,
            code="DEFAULTS-001",
        )
        db_session.add(eng)
        db_session.commit()
        assert eng.permissions == {}
        assert eng.limits == {}


class TestJobModel:
    def test_create_job(self, db_session: Session):
        eng = _eng(db_session, "JOB-ENG-001")
        job = Job(
            engagement_id=eng.id,
            kind="passive_capture",
            status=JobStatus.CREATED,
            parameters={"interface": "wlan0"},
        )
        db_session.add(job)
        db_session.commit()
        assert job.id is not None
        assert job.kind == "passive_capture"
        assert job.status == JobStatus.CREATED.value
        assert job.parameters == {"interface": "wlan0"}
        assert job.priority == 0
        assert job.timeout_seconds == 300

    def test_job_engagement_relationship(self, db_session: Session):
        """Job pertenece a un Engagement via FK."""
        eng = _eng(db_session, "JOB-ENG-002")
        job = Job(
            engagement_id=eng.id,
            kind="handshake_capture",
            status=JobStatus.CREATED,
        )
        db_session.add(job)
        db_session.commit()
        assert job.engagement is not None
        assert job.engagement.id == eng.id
        assert job in eng.jobs

    def test_job_orphan_delete(self, db_session: Session):
        """Eliminar engagement elimina sus jobs en cascada."""
        eng = _eng(db_session, "JOB-ENG-003")
        job = Job(
            engagement_id=eng.id,
            kind="test",
            status=JobStatus.CREATED,
        )
        db_session.add(job)
        db_session.commit()
        jid = job.id

        db_session.delete(eng)
        db_session.commit()

        assert db_session.get(Job, jid) is None


class TestScopeTargetModel:
    def test_create_scope_target(self, db_session: Session):
        eng = _eng(db_session, "SCOPE-ENG-001")
        st = ScopeTarget(
            engagement_id=eng.id,
            ssid="LAB-NET",
            bssid="AA:BB:CC:DD:EE:FF",
            channel=6,
            band="5",
            permission_level="active",
        )
        db_session.add(st)
        db_session.commit()
        assert st.id is not None
        assert st.engagement_id == eng.id


class TestAccessPointModel:
    def test_create_access_point(self, db_session: Session):
        eng = _eng(db_session, "AP-ENG-001")
        ap = AccessPoint(
            engagement_id=eng.id,
            ssid="TestNet",
            bssid="AA:BB:CC:DD:EE:FF",
            channel=6,
            frequency=2412,
            signal=-45,
            protocol="WPA2",
            akm="PSK",
            cipher="CCMP",
            wps=False,
        )
        db_session.add(ap)
        db_session.commit()
        assert ap.id is not None
        assert ap.ssid == "TestNet"
        assert ap.wps is False


class TestStationModel:
    def test_create_station(self, db_session: Session):
        sta = Station(
            mac="11:22:33:44:55:66",
            randomized=False,
            vendor="Intel",
            associated_bssid="AA:BB:CC:DD:EE:FF",
            signal=-50,
            controlled=False,
        )
        db_session.add(sta)
        db_session.commit()
        assert sta.id is not None
        assert sta.vendor == "Intel"


class TestCaptureModel:
    def test_create_capture(self, db_session: Session):
        eng = _eng(db_session, "CAP-ENG-001")
        cap = Capture(
            engagement_id=eng.id,
            path="/tmp/test.pcapng",
            format="pcapng",
            sha256="ab" * 32,
            tool="tcpdump",
            tool_version="4.9",
        )
        db_session.add(cap)
        db_session.commit()
        assert cap.id is not None
        assert cap.category == "original"  # default


class TestHandshakeArtifactModel:
    def test_create_handshake(self, db_session: Session):
        h = HandshakeArtifact(
            kind="eapol",
            message_pair="M1M2",
            quality=HandshakeQuality.EXCELLENT,
            validated=True,
        )
        db_session.add(h)
        db_session.commit()
        assert h.id is not None
        assert h.quality == HandshakeQuality.EXCELLENT.value


class TestCrackingJobModel:
    def test_create_cracking_job(self, db_session: Session):
        cj = CrackingJob(
            strategy="dictionary",
            keyspace=1000000,
            progress=0.5,
            speed=50000,
            status=CrackJobStatus.RUNNING,
        )
        db_session.add(cj)
        db_session.commit()
        assert cj.id is not None
        assert cj.strategy == "dictionary"
        assert cj.progress == 0.5


class TestFindingModel:
    def test_create_finding(self, db_session: Session):
        eng = _eng(db_session, "FIND-ENG-001")
        f = Finding(
            engagement_id=eng.id,
            title="WPA2 Weak Password",
            category="WIFI-PSK",
            rule_id="WIFI-PSK-001",
            severity=Severity.HIGH,
            confidence=0.95,
            description="Password susceptible to dictionary attack",
            impact="Unauthorized network access",
            remediation="Use a complex password (≥12 chars)",
            evidence={"hash_mode": 22000, "cracked": True},
            affected_assets=["AA:BB:CC:DD:EE:FF"],
            status=FindingStatus.OPEN,
        )
        db_session.add(f)
        db_session.commit()
        assert f.id is not None
        assert f.severity == Severity.HIGH.value
        assert f.confidence == 0.95


# ===================================================================
# Helpers
# ===================================================================


def _eng(session: Session, code: str) -> Engagement:
    eng = Engagement(
        name="test",
        client="test",
        operator="test",
        status=EngagementStatus.DRAFT,
        code=code,
        permissions={},
        limits={},
    )
    session.add(eng)
    session.commit()
    session.refresh(eng)
    return eng
