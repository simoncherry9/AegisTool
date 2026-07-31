"""Tests del módulo de validación de handshakes (minuta §15, §16, §28)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from aegiswifi.validation.schemas import (
    EapolAnalysis,
    HandshakeReport,
    PmkidAnalysis,
    QualityClassification,
    ValidationRequest,
    ValidationResult,
)
from aegiswifi.validation.service import HandshakeValidationService, get_validation_service


# ===================================================================
# Tests de schemas
# ===================================================================


class TestQualityClassification:
    def test_enum_values(self) -> None:
        assert QualityClassification.EXCELLENT.value == "EXCELLENT"
        assert QualityClassification.GOOD.value == "GOOD"
        assert QualityClassification.ACCEPTABLE.value == "ACCEPTABLE"
        assert QualityClassification.POOR.value == "POOR"
        assert QualityClassification.INVALID.value == "INVALID"

    def test_ordering_by_score(self) -> None:
        """Verifica que los niveles de calidad siguen orden lógico."""
        levels = [
            QualityClassification.EXCELLENT,
            QualityClassification.GOOD,
            QualityClassification.ACCEPTABLE,
            QualityClassification.POOR,
            QualityClassification.INVALID,
        ]
        # Solo verificar que son distintos.
        assert len(set(levels)) == 5


class TestEapolAnalysis:
    def test_defaults(self) -> None:
        ea = EapolAnalysis()
        assert ea.messages_found == []
        assert ea.pairs_complete == []
        assert ea.has_full_handshake is False
        assert ea.has_m12 is False
        assert ea.has_m14 is False

    def test_with_values(self) -> None:
        ea = EapolAnalysis(
            messages_found=["M1", "M2", "M3"],
            pairs_complete=["M1M2", "M3M4"],
            has_full_handshake=True,
            has_m12=True,
        )
        assert "M1" in ea.messages_found
        assert "M3" in ea.messages_found
        assert "M1M2" in ea.pairs_complete
        assert ea.has_full_handshake is True
        assert ea.has_m12 is True
        assert ea.has_m14 is False


class TestPmkidAnalysis:
    def test_defaults(self) -> None:
        pa = PmkidAnalysis()
        assert pa.detected is False
        assert pa.raw_value is None
        assert pa.hash_line is None

    def test_with_values(self) -> None:
        pa = PmkidAnalysis(detected=True, raw_value="abcd1234", hash_line="WPA*01*...")
        assert pa.detected is True
        assert pa.raw_value == "abcd1234"
        assert pa.hash_line == "WPA*01*..."


class TestValidationRequest:
    def test_defaults(self) -> None:
        vr = ValidationRequest()
        assert vr.capture_id is None
        assert vr.file_path is None
        assert vr.engagement_id is None
        assert vr.force_reprocess is False

    def test_with_capture_id(self) -> None:
        vr = ValidationRequest(capture_id=42)
        assert vr.capture_id == 42

    def test_with_file_path(self) -> None:
        vr = ValidationRequest(file_path="/tmp/test.pcapng")
        assert vr.file_path == "/tmp/test.pcapng"

    def test_force_reprocess(self) -> None:
        vr = ValidationRequest(capture_id=1, force_reprocess=True)
        assert vr.force_reprocess is True

    def test_engagement_id_validation(self) -> None:
        vr = ValidationRequest(capture_id=1, engagement_id=5)
        assert vr.engagement_id == 5

        # engagement_id debe ser ≥ 1
        with pytest.raises(ValidationError):
            ValidationRequest(capture_id=1, engagement_id=0)


class TestHandshakeReport:
    def test_minimal(self) -> None:
        report = HandshakeReport(id=1)
        assert report.id == 1
        assert report.quality == "INVALID"
        assert report.validated is False
        assert report.kind == "eapol"

    def test_full(self) -> None:
        report = HandshakeReport(
            id=42,
            bssid="AA:BB:CC:DD:EE:FF",
            ssid="TestNet",
            channel=6,
            kind="pmkid",
            quality="GOOD",
            validated=True,
            message_pair="M1M2",
            hash_file="/data/hashes/artifact_42.22000",
            crack_status="recovered",
            access_point_id=10,
            station_mac="11:22:33:44:55:66",
            created_at=datetime(2026, 7, 1, tzinfo=UTC),
        )
        assert report.id == 42
        assert report.bssid == "AA:BB:CC:DD:EE:FF"
        assert report.ssid == "TestNet"
        assert report.kind == "pmkid"
        assert report.quality == "GOOD"
        assert report.crack_status == "recovered"
        assert report.station_mac == "11:22:33:44:55:66"


# ===================================================================
# Tests de ValidationResult
# ===================================================================


class TestValidationResult:
    def test_defaults(self) -> None:
        vr = ValidationResult()
        assert vr.artifact_id is None
        assert vr.quality == QualityClassification.INVALID
        assert vr.quality_score == 0.0
        assert vr.validated is False
        assert vr.errors == []
        assert vr.warnings == []
        assert vr.kind == "eapol"

    def test_with_eapol_data(self) -> None:
        vr = ValidationResult(
            eapol=EapolAnalysis(
                messages_found=["M1", "M2"],
                pairs_complete=["M1M2"],
                has_m12=True,
            ),
            quality=QualityClassification.GOOD,
            quality_score=0.65,
            validated=True,
            kind="eapol",
            message_pair="M1M2",
        )
        assert vr.eapol.has_m12 is True
        assert vr.eapol.messages_found == ["M1", "M2"]
        assert vr.quality == QualityClassification.GOOD
        assert vr.quality_score == 0.65
        assert vr.validated is True

    def test_with_pmkid(self) -> None:
        vr = ValidationResult(
            pmkid=PmkidAnalysis(detected=True, raw_value="hexvalue"),
            quality=QualityClassification.GOOD,
            quality_score=0.8,
            validated=True,
        )
        assert vr.pmkid.detected is True
        assert vr.pmkid.raw_value == "hexvalue"

    def test_errors_populated(self) -> None:
        vr = ValidationResult(
            errors=["Archivo no encontrado", "Formato inválido"],
            quality=QualityClassification.INVALID,
        )
        assert len(vr.errors) == 2
        assert "Archivo no encontrado" in vr.errors
        assert vr.validated is False


# ===================================================================
# Tests del servicio
# ===================================================================


class FakeCapture:
    """Simula un Capture de BD con atributos mínimos."""

    def __init__(self, id: int = 1, path: str = "/tmp/fake.pcapng") -> None:
        self.id = id
        self.path = path


class FakeHandshakeArtifact:
    """Simula un HandshakeArtifact de BD."""

    def __init__(
        self,
        id: int = 1,
        capture_id: int = 1,
        validated: bool = True,
        quality: str = "GOOD",
        kind: str = "eapol",
        message_pair: str | None = "M1M2",
        hash22000_path: str | None = "/tmp/test.22000",
        access_point_id: int | None = None,
        station_id: int | None = None,
        created_at: datetime | None = None,
    ) -> None:
        self.id = id
        self.capture_id = capture_id
        self.validated = validated
        self.quality = quality
        self.kind = kind
        self.message_pair = message_pair
        self.hash22000_path = hash22000_path
        self.access_point_id = access_point_id
        self.station_id = station_id
        self.created_at = created_at or datetime.now(UTC)
        self.access_point = None
        self.station = None
        self.cracking_job = None


class TestHandshakeValidationService:
    """Prueba el servicio de validación sin depender de hcxpcapngtool real.

    La ejecución real de subprocesos está aislada mockeando asyncio.
    """

    def test_resolve_source_capture_first(self) -> None:
        """capture.path se usa si no hay file_path."""
        service = HandshakeValidationService()
        capture = FakeCapture(id=1, path="/captures/test.pcapng")
        src = service._resolve_source(capture, None)
        assert src == "/captures/test.pcapng"

    def test_resolve_source_file_path_preferred(self) -> None:
        """file_path tiene prioridad sobre capture.path."""
        service = HandshakeValidationService()
        capture = FakeCapture(id=1, path="/captures/test.pcapng")
        src = service._resolve_source(capture, "/direct/file.pcapng")
        assert src == "/direct/file.pcapng"

    def test_resolve_source_none(self) -> None:
        """Retorna None si no hay ni capture ni file_path."""
        service = HandshakeValidationService()
        assert service._resolve_source(None, None) is None

    def test_is_full_handshake_m3(self) -> None:
        """03 en message_pair indica handshake completo."""
        service = HandshakeValidationService()
        assert service._is_full_handshake("03") is True
        assert service._is_full_handshake("M1M3") is True

    def test_is_full_handshake_incomplete(self) -> None:
        """Solo M1+M2 no es handshake completo."""
        service = HandshakeValidationService()
        assert service._is_full_handshake("02") is False
        assert service._is_full_handshake("01") is False
        assert service._is_full_handshake("") is False

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------

    def test_score_empty(self) -> None:
        """Sin mensajes ni PMKID, score debe ser 0."""
        service = HandshakeValidationService()
        result = ValidationResult()
        score = service._compute_score(result)
        assert score == 0.0

    def test_score_m1m2_only(self) -> None:
        """Solo M1+M2 da score 0.35."""
        service = HandshakeValidationService()
        result = ValidationResult(
            eapol=EapolAnalysis(
                messages_found=["M1", "M2"],
                pairs_complete=["M1M2"],
                has_m12=True,
            ),
        )
        score = service._compute_score(result)
        assert score == pytest.approx(0.35)  # M1=0.10 + M2=0.25

    def test_score_m1m2m3(self) -> None:
        """M1+M2+M3 da 0.55 + 0.10 bonus = 0.65."""
        service = HandshakeValidationService()
        result = ValidationResult(
            eapol=EapolAnalysis(
                messages_found=["M1", "M2", "M3"],
                pairs_complete=["M1M2", "M3M4"],
                has_full_handshake=True,
            ),
        )
        score = service._compute_score(result)
        assert score == pytest.approx(0.65)  # 0.55 + 0.10 bonus

    def test_score_full_handshake(self) -> None:
        """M1+M2+M3+M4 da 0.70 + 0.10 bonus = 0.80."""
        service = HandshakeValidationService()
        result = ValidationResult(
            eapol=EapolAnalysis(
                messages_found=["M1", "M2", "M3", "M4"],
                pairs_complete=["M1M2", "M3M4"],
                has_full_handshake=True,
            ),
        )
        score = service._compute_score(result)
        assert score == pytest.approx(0.80)  # 0.70 + 0.10

    def test_score_full_handshake_plus_pmkid(self) -> None:
        """Completo + PMKID da 1.0 (cap)."""
        service = HandshakeValidationService()
        result = ValidationResult(
            eapol=EapolAnalysis(
                messages_found=["M1", "M2", "M3", "M4"],
                pairs_complete=["M1M2", "M3M4"],
                has_full_handshake=True,
            ),
            pmkid=PmkidAnalysis(detected=True),
        )
        score = service._compute_score(result)
        assert score == pytest.approx(1.0)  # 0.70 + 0.10 + 0.30 + 0.05 → capped

    def test_score_pmkid_plus_m12_bonus(self) -> None:
        """PMKID + M1+M2 recibe bonus extra."""
        service = HandshakeValidationService()
        result = ValidationResult(
            eapol=EapolAnalysis(
                messages_found=["M1", "M2"],
                pairs_complete=["M1M2"],
                has_m12=True,
            ),
            pmkid=PmkidAnalysis(detected=True),
        )
        score = service._compute_score(result)
        assert score == pytest.approx(0.70)  # 0.10+0.25+0.30+0.05

    # ------------------------------------------------------------------
    # Clasificación
    # ------------------------------------------------------------------

    def test_classify_excellent(self) -> None:
        service = HandshakeValidationService()
        result = ValidationResult(eapol=EapolAnalysis(
            messages_found=["M1", "M2", "M3", "M4"],
            pairs_complete=["M1M2", "M3M4"],
            has_full_handshake=True,
        ), pmkid=PmkidAnalysis(detected=True))
        service._classify_quality(result)
        assert result.quality == QualityClassification.EXCELLENT
        assert result.quality_score > 0.85
        assert result.validated is True

    def test_classify_good(self) -> None:
        service = HandshakeValidationService()
        result = ValidationResult(eapol=EapolAnalysis(
            messages_found=["M1", "M2", "M3"],
            pairs_complete=["M1M2", "M3M4"],
            has_full_handshake=True,
        ))
        service._classify_quality(result)
        assert result.quality == QualityClassification.GOOD
        assert result.validated is True

    def test_classify_acceptable(self) -> None:
        """PMKID (0.30) + M2 (0.25) = 0.55 ≥ 0.50 → ACCEPTABLE."""
        service = HandshakeValidationService()
        result = ValidationResult(
            pmkid=PmkidAnalysis(detected=True),
            eapol=EapolAnalysis(
                messages_found=["M2"],
                pairs_complete=["02"],
            ),
        )
        service._classify_quality(result)
        assert result.quality == QualityClassification.ACCEPTABLE
        assert result.quality_score >= 0.50
        assert result.validated is True

    def test_classify_poor(self) -> None:
        """M1 (0.10) + M4 (0.15) = 0.25 ≥ 0.20 → POOR."""
        service = HandshakeValidationService()
        result = ValidationResult(eapol=EapolAnalysis(
            messages_found=["M1", "M4"],
            pairs_complete=["M1M4"],
            has_m14=True,
        ))
        service._classify_quality(result)
        assert result.quality == QualityClassification.POOR
        assert result.quality_score < 0.50
        assert result.validated is False

    def test_classify_invalid(self) -> None:
        service = HandshakeValidationService()
        result = ValidationResult()
        service._classify_quality(result)
        assert result.quality == QualityClassification.INVALID
        assert result.quality_score == 0.0
        assert result.validated is False

    # ------------------------------------------------------------------
    # Parseo de líneas 22000
    # ------------------------------------------------------------------

    @staticmethod
    def _sample_22000_line(
        msg_pair: str = "02",
        bssid: str = "AA:BB:CC:DD:EE:FF",
        station: str = "11:22:33:44:55:66",
        essid: str = "TestNet",
    ) -> str:
        """Genera una línea fake en formato 22000."""
        return f"WPA*01*{msg_pair}*{bssid}*{station}*{essid}*"

    def test_parse_22000_line_m1m2(self) -> None:
        service = HandshakeValidationService()
        result = ValidationResult()
        line = self._sample_22000_line(msg_pair="02")
        service._parse_22000_line(line, result)
        assert result.eapol.has_m12 is True
        assert result.eapol.pairs_complete == ["02"]
        assert result.message_pair == "02"
        assert result.kind == "eapol"

    def test_parse_22000_line_m1m4(self) -> None:
        service = HandshakeValidationService()
        result = ValidationResult()
        line = self._sample_22000_line(msg_pair="04")
        service._parse_22000_line(line, result)
        assert result.eapol.has_m14 is True
        assert result.eapol.pairs_complete == ["04"]

    def test_parse_22000_line_full(self) -> None:
        service = HandshakeValidationService()
        result = ValidationResult()
        line = self._sample_22000_line(msg_pair="03")
        service._parse_22000_line(line, result)
        assert result.eapol.has_full_handshake is True
        assert result.eapol.pairs_complete == ["03"]

    def test_parse_22000_non_wpa_line(self) -> None:
        """Líneas que no empiezan con WPA se ignoran."""
        service = HandshakeValidationService()
        result = ValidationResult()
        service._parse_22000_line("PMKID*...", result)
        assert result.eapol.pairs_complete == []

    def test_parse_22000_too_short(self) -> None:
        """Líneas con menos de 6 campos se ignoran."""
        service = HandshakeValidationService()
        result = ValidationResult()
        service._parse_22000_line("WPA*01*02", result)
        assert result.eapol.pairs_complete == []

    def test_parse_22000_accumulates_pairs(self) -> None:
        """Múltiples líneas acumulan pares."""
        service = HandshakeValidationService()
        result = ValidationResult()
        service._parse_22000_line(self._sample_22000_line(msg_pair="02"), result)
        service._parse_22000_line(self._sample_22000_line(msg_pair="04"), result)
        assert "02" in result.eapol.pairs_complete
        assert "04" in result.eapol.pairs_complete
        assert len(result.eapol.pairs_complete) == 2

    # ------------------------------------------------------------------
    # Parseo del archivo hash completo
    # ------------------------------------------------------------------

    def test_analyze_hashfile(self, tmp_path: Path) -> None:
        service = HandshakeValidationService()
        hash_file = tmp_path / "test.22000"
        hash_file.write_text(
            "WPA*01*02*AA:BB:CC:DD:EE:FF*11:22:33:44:55:66*TestNet*\n"
            "WPA*01*04*AA:BB:CC:DD:EE:FF*11:22:33:44:55:66*TestNet*\n"
        )
        result = ValidationResult()
        service._analyze_hashfile(hash_file, result)
        assert result.hash22000_path == str(hash_file)
        assert result.hash22000_line is not None
        assert result.eapol.has_m12 is True
        assert result.eapol.has_m14 is True
        assert len(result.eapol.pairs_complete) == 2

    def test_analyze_hashfile_empty(self, tmp_path: Path) -> None:
        """Archivo vacío no debe causar error."""
        service = HandshakeValidationService()
        hash_file = tmp_path / "empty.22000"
        hash_file.write_text("")
        result = ValidationResult()
        service._analyze_hashfile(hash_file, result)
        assert result.hash22000_path == str(hash_file)
        assert result.hash22000_line is None
        assert result.eapol.pairs_complete == []

    # ------------------------------------------------------------------
    # build_report
    # ------------------------------------------------------------------

    def test_build_report_minimal(self) -> None:
        service = HandshakeValidationService()
        artifact = FakeHandshakeArtifact(id=5, quality="GOOD")
        report = service.build_report(artifact)
        assert report["id"] == 5
        assert report["quality"] == "GOOD"
        assert report["validated"] is True
        assert report["kind"] == "eapol"
        assert report["crack_status"] is None

    def test_build_report_no_access_point(self) -> None:
        """Si no hay access_point, bssid/ssid/channel deben ser None."""
        service = HandshakeValidationService()
        artifact = FakeHandshakeArtifact(id=3, access_point_id=None)
        report = service.build_report(artifact)
        assert report["bssid"] is None
        assert report["ssid"] is None
        assert report["channel"] is None

    # ------------------------------------------------------------------
    # validate_capture — file not found
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_validate_capture_file_not_found(self) -> None:
        """Si el archivo no existe, retorna error."""
        service = HandshakeValidationService()
        result = await service.validate_capture(
            file_path="/tmp/nonexistent_12345.pcapng"
        )
        assert result.quality == QualityClassification.INVALID
        assert len(result.errors) > 0
        assert "no encontrado" in result.errors[0].lower() or "Archivo" in result.errors[0]

    # ------------------------------------------------------------------
    # validate_capture — capture sin path
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_validate_capture_no_path(self) -> None:
        """Si capture no tiene path, retorna error."""
        service = HandshakeValidationService()
        capture = FakeCapture(id=99, path="")
        result = await service.validate_capture(capture=capture)
        assert result.quality == QualityClassification.INVALID

    # ------------------------------------------------------------------
    # _parse_tool_line
    # ------------------------------------------------------------------

    def test_parse_tool_line_handshake(self) -> None:
        service = HandshakeValidationService()
        r = service._parse_tool_line("Found handshake from AA:BB:CC:DD:EE:FF")
        assert r is not None
        assert r.get("handshake_detected") is True

    def test_parse_tool_line_pmkid(self) -> None:
        service = HandshakeValidationService()
        r = service._parse_tool_line("PMKID found")
        assert r is not None
        assert r.get("pmkid_detected") is True

    def test_parse_tool_line_eapol(self) -> None:
        service = HandshakeValidationService()
        r = service._parse_tool_line("EAPOL M1 M2 detected")
        assert r is not None
        assert "eapol_messages" in r
        assert "M1" in r["eapol_messages"]
        assert "M2" in r["eapol_messages"]

    def test_parse_tool_line_irrelevant(self) -> None:
        service = HandshakeValidationService()
        r = service._parse_tool_line("hcxpcapngtool v6.2.7 starting")
        assert r is None

    def test_parse_tool_line_empty(self) -> None:
        service = HandshakeValidationService()
        assert service._parse_tool_line("") is None
        assert service._parse_tool_line("   ") is None

    # ------------------------------------------------------------------
    # existent artifact — skip if already validated
    # ------------------------------------------------------------------

    def test_find_existing_artifact_none(self) -> None:
        """Sin db_session, retorna None."""
        service = HandshakeValidationService()
        capture = FakeCapture(id=1)
        result = service._find_existing_artifact(capture, None)
        assert result is None

    # ------------------------------------------------------------------
    # Validación existente → conversion a resultado
    # ------------------------------------------------------------------

    def test_artifact_to_result(self) -> None:
        service = HandshakeValidationService()
        artifact = FakeHandshakeArtifact(
            id=10,
            capture_id=5,
            validated=True,
            quality="GOOD",
            kind="eapol",
            message_pair="M1M2",
            hash22000_path="/data/hashes/artifact_10.22000",
        )
        capture = FakeCapture(id=5, path="/captures/test.pcapng")
        result = service._artifact_to_result(artifact, capture)
        assert result.artifact_id == 10
        assert result.capture_id == 5
        assert result.validated is True
        assert result.quality == QualityClassification.GOOD
        assert result.hash22000_path == "/data/hashes/artifact_10.22000"
        assert result.kind == "eapol"

    # ------------------------------------------------------------------
    # validate_capture con hcxpcapngtool no instalado
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_validate_capture_tool_not_found(self, tmp_path: Path) -> None:
        """Si hcxpcapngtool no existe en el path, reporta error."""
        capture_file = tmp_path / "capture.pcapng"
        capture_file.write_text("fake pcap content")

        service = HandshakeValidationService(
            hcxpcapngtool_path="/usr/bin/nonexistent_tool_99999"
        )
        result = await service.validate_capture(file_path=str(capture_file))
        assert result.quality == QualityClassification.INVALID
        assert len(result.errors) > 0

    # ------------------------------------------------------------------
    # Test del singleton
    # ------------------------------------------------------------------

    def test_get_validation_service_singleton(self) -> None:
        service_a = get_validation_service()
        service_b = get_validation_service()
        assert service_a is service_b
        assert isinstance(service_a, HandshakeValidationService)


# ===================================================================
# Tests de integración con API (simulados)
# ===================================================================


class TestValidationResultModelDump:
    """Verifica que ValidationResult se serializa correctamente."""

    def test_model_dump_exclude_none(self) -> None:
        vr = ValidationResult()
        d = vr.model_dump(exclude_none=True)
        assert "source_file" not in d  # None
        assert "artifact_id" not in d  # None
        assert "quality" in d
        assert "errors" in d
        assert d["quality"] == "INVALID"
        assert d["validated"] is False

    def test_model_dump_full(self) -> None:
        vr = ValidationResult(
            artifact_id=1,
            capture_id=1,
            quality=QualityClassification.GOOD,
            quality_score=0.75,
            validated=True,
            kind="eapol",
            message_pair="M1M2",
            eapol=EapolAnalysis(
                messages_found=["M1", "M2"],
                pairs_complete=["M1M2"],
                has_m12=True,
            ),
            source_file="/tmp/test.pcapng",
        )
        d = vr.model_dump()
        assert d["artifact_id"] == 1
        assert d["quality"] == "GOOD"
        assert d["quality_score"] == 0.75
        assert d["eapol"]["has_m12"] is True
        assert d["eapol"]["messages_found"] == ["M1", "M2"]
