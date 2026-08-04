"""Tests del módulo de evidencia (Fase 2b, minuta §30).

Cubre:
  - EvidenceStore: store_artifact con verificación SHA-256.
  - EvidenceStore: FileExistsError en duplicado.
  - EvidenceStore.verify_integrity.
  - evidence service: CRUD con BD.
  - evidence API: endpoints GET / DELETE / download.
"""

from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from aegiswifi.core.exceptions import NotFound
from aegiswifi.database.models import Capture, Engagement, EngagementStatus
from aegiswifi.evidence.service import get_evidence, list_evidence
from aegiswifi.evidence.store import EvidenceStore

_TMP = tempfile.gettempdir()

# ===================================================================
# Fixtures helpers
# ===================================================================


def _create_engagement(session: Session) -> Engagement:
    eng = Engagement(
        name="evidence-test",
        client="test-client",
        operator="test-operator",
        status=EngagementStatus.ACTIVE,
        code="EVI-TEST-001",
    )
    session.add(eng)
    session.commit()
    session.refresh(eng)
    return eng


def _create_evidence_in_db(session: Session, **overrides: object) -> Capture:
    """Crea un registro Capture directamente en BD (sin copiar archivo)."""
    capture = Capture(
        engagement_id=overrides.get("engagement_id", 1),
        job_id=overrides.get("job_id"),
        category=overrides.get("category", "original"),
        path=overrides.get("path", f"{_TMP}/test_evidencia.pcapng"),
        format=overrides.get("format", "pcapng"),
        sha256=overrides.get("sha256", "dummy" * 16),
        original_filename=overrides.get("original_filename", "test.pcapng"),
        size_bytes=overrides.get("size_bytes", 1024),
        tool=overrides.get("tool", "tcpdump"),
    )
    session.add(capture)
    session.commit()
    session.refresh(capture)
    return capture


def _make_temp_file(content: bytes = b"fake pcap data\n" * 1000) -> Path:
    """Crea un archivo temporal para usar como fuente de evidencia."""
    fd, path = tempfile.mkstemp(suffix=".pcapng")
    os.write(fd, content)
    os.close(fd)
    return Path(path)


# ===================================================================
# EvidenceStore Tests
# ===================================================================


class TestEvidenceStore:
    @pytest.mark.asyncio
    async def test_store_artifact_creates_file_and_record(self, db_session: Session):
        """store_artifact copia el archivo y crea un Capture en BD."""
        source = _make_temp_file(b"test pcap data " * 500)
        engagement = _create_engagement(db_session)

        def sf() -> Session:
            return db_session

        store = EvidenceStore(evidence_dir=Path(tempfile.mkdtemp()), session_factory=sf)
        capture = await store.store_artifact(
            source_path=source,
            original_filename="capture.pcapng",
            engagement_id=engagement.id,
            job_id=None,
            category="original",
            format="pcapng",
            tool="tcpdump",
        )

        assert capture.id is not None
        assert capture.engagement_id == engagement.id
        assert capture.category == "original"
        assert capture.format == "pcapng"
        assert capture.tool == "tcpdump"
        assert capture.sha256 is not None
        assert len(capture.sha256) == 64  # SHA-256 hex
        assert capture.size_bytes == len(b"test pcap data " * 500)

        # Verificar archivo en disco
        dest = Path(capture.path)
        assert dest.exists()  # noqa: ASYNC240
        assert dest.read_bytes() == source.read_bytes()  # noqa: ASYNC240

    @pytest.mark.asyncio
    async def test_store_artifact_sha256_matches(self, db_session: Session):
        """El SHA-256 almacenado coincide con el hash del archivo."""
        content = b"deterministic content for sha256 check " * 100
        source = _make_temp_file(content)
        engagement = _create_engagement(db_session)

        expected_sha = hashlib.sha256(content).hexdigest()

        def sf() -> Session:
            return db_session

        store = EvidenceStore(evidence_dir=Path(tempfile.mkdtemp()), session_factory=sf)
        capture = await store.store_artifact(
            source_path=source,
            original_filename="sha_check.pcapng",
            engagement_id=engagement.id,
            job_id=None,
            category="original",
            format="pcapng",
            tool="test",
        )

        assert capture.sha256 == expected_sha

    @pytest.mark.asyncio
    async def test_store_artifact_duplicate_raises(self, db_session: Session):
        """Sobrescribir un archivo de evidencia lanza FileExistsError."""
        source = _make_temp_file(b"original data")
        engagement = _create_engagement(db_session)

        def sf() -> Session:
            return db_session

        evidence_dir = Path(tempfile.mkdtemp())
        store = EvidenceStore(evidence_dir=evidence_dir, session_factory=sf)

        await store.store_artifact(
            source_path=source,
            original_filename="unique.pcapng",
            engagement_id=engagement.id,
            job_id=None,
            category="original",
            format="pcapng",
            tool="test",
        )

        # Segundo intento con mismo source (mismo nombre destino) debe fallar.
        with pytest.raises(FileExistsError, match="ya existe"):
            await store.store_artifact(
                source_path=source,
                original_filename="unique.pcapng",
                engagement_id=engagement.id,
                job_id=None,
                category="original",
                format="pcapng",
                tool="test",
            )

    def test_verify_integrity_ok(self):
        """verify_integrity retorna True para un archivo íntegro."""
        content = b"integrity test data"
        source = _make_temp_file(content)
        expected_sha = hashlib.sha256(content).hexdigest()
        assert EvidenceStore.verify_integrity(source, expected_sha) is True

    def test_verify_integrity_fail(self):
        """verify_integrity retorna False si el hash no coincide."""
        content = b"integrity test data"
        source = _make_temp_file(content)
        wrong_sha = "00" * 32
        assert EvidenceStore.verify_integrity(source, wrong_sha) is False

    def test_verify_integrity_missing_file(self):
        """verify_integrity lanza FileNotFoundError si el archivo no existe."""
        missing = Path(tempfile.mkdtemp()) / "nonexistent.pcapng"
        with pytest.raises(FileNotFoundError):
            EvidenceStore.verify_integrity(missing, "00" * 32)


# ===================================================================
# Evidence Service Tests
# ===================================================================


class TestEvidenceService:
    def test_get_evidence(self, db_session: Session):
        eng = _create_engagement(db_session)
        cap = _create_evidence_in_db(db_session, engagement_id=eng.id)
        fetched = get_evidence(db_session, cap.id)
        assert fetched.id == cap.id
        assert fetched.sha256 == cap.sha256

    def test_get_evidence_not_found(self, db_session: Session):
        with pytest.raises(NotFound):
            get_evidence(db_session, 9999)

    def test_list_evidence(self, db_session: Session):
        eng = _create_engagement(db_session)
        _create_evidence_in_db(db_session, engagement_id=eng.id)
        _create_evidence_in_db(db_session, engagement_id=eng.id)
        all_ev = list_evidence(db_session)
        assert len(all_ev) >= 2

    def test_list_evidence_filter_engagement(self, db_session: Session):
        eng1 = _create_engagement(db_session)
        eng2 = Engagement(
            name="other-eng",
            client="other",
            operator="op",
            status=EngagementStatus.ACTIVE,
            code="EVI-TEST-002",
        )
        db_session.add(eng2)
        db_session.commit()
        db_session.refresh(eng2)

        _create_evidence_in_db(db_session, engagement_id=eng1.id)
        _create_evidence_in_db(db_session, engagement_id=eng2.id)

        filtered = list_evidence(db_session, engagement_id=eng1.id)
        assert len(filtered) == 1
        assert filtered[0].engagement_id == eng1.id

    def test_list_evidence_filter_category(self, db_session: Session):
        eng = _create_engagement(db_session)
        _create_evidence_in_db(db_session, engagement_id=eng.id, category="original")
        _create_evidence_in_db(db_session, engagement_id=eng.id, category="log")

        filtered = list_evidence(db_session, category="log")
        assert all(c.category == "log" for c in filtered)


# ===================================================================
# Evidence API Tests
# ===================================================================


class TestEvidenceAPI:
    def test_list_evidence_api(self, db_session: Session, client: TestClient):
        eng = _create_engagement(db_session)
        _create_evidence_in_db(db_session, engagement_id=eng.id)
        resp = client.get("/api/v1/evidence")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_get_evidence_api(self, db_session: Session, client: TestClient):
        eng = _create_engagement(db_session)
        cap = _create_evidence_in_db(db_session, engagement_id=eng.id)
        resp = client.get(f"/api/v1/evidence/{cap.id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == cap.id

    def test_get_evidence_404(self, client: TestClient):
        resp = client.get("/api/v1/evidence/9999")
        assert resp.status_code == 404

    def test_download_evidence(self, db_session: Session, client: TestClient):
        """GET /evidence/{id}/download retorna el archivo."""
        eng = _create_engagement(db_session)
        source = _make_temp_file(b"download test content")
        # Crear capture real con archivo en disco
        from aegiswifi.evidence.store import EvidenceStore

        def sf() -> Session:
            return db_session

        store = EvidenceStore(evidence_dir=Path(tempfile.mkdtemp()), session_factory=sf)
        import asyncio

        capture = asyncio.run(
            store.store_artifact(
                source_path=source,
                original_filename="download.pcapng",
                engagement_id=eng.id,
                job_id=None,
                category="original",
                format="pcapng",
                tool="test",
            )
        )
        resp = client.get(f"/api/v1/evidence/{capture.id}/download")
        assert resp.status_code == 200
        assert resp.headers.get("content-type") == "application/octet-stream"

    def test_download_evidence_file_missing(self, db_session: Session, client: TestClient):
        """Descargar evidencia cuyo archivo no existe retorna 404."""
        eng = _create_engagement(db_session)
        missing = f"{_TMP}/missing.pcapng"
        cap = _create_evidence_in_db(db_session, engagement_id=eng.id, path=missing)
        resp = client.get(f"/api/v1/evidence/{cap.id}/download")
        assert resp.status_code == 404

    def test_evidence_cannot_be_deleted_api(self, db_session: Session, client: TestClient):
        eng = _create_engagement(db_session)
        cap = _create_evidence_in_db(db_session, engagement_id=eng.id)
        resp = client.delete(f"/api/v1/evidence/{cap.id}")
        assert resp.status_code == 405
        assert get_evidence(db_session, cap.id).id == cap.id
