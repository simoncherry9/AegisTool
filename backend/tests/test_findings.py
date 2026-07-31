"""Tests del motor de hallazgos (minuta §29, §28)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from aegiswifi.database.models import (
    CrackJobStatus,
    CrackingJob,
    Engagement,
    Finding,
    HandshakeArtifact,
)
from aegiswifi.findings.engine import FindingsEngine, get_findings_engine
from aegiswifi.findings.schemas import (
    EngineResult,
    FindingCreate,
    FindingRead,
    FindingRule,
    FindingStatus,
    FindingSummary,
    FindingUpdate,
    Severity,
)


# ===================================================================
# Tests de schemas
# ===================================================================


class TestSeverity:
    def test_values(self) -> None:
        assert Severity.INFO.value == "INFO"
        assert Severity.LOW.value == "LOW"
        assert Severity.MEDIUM.value == "MEDIUM"
        assert Severity.HIGH.value == "HIGH"
        assert Severity.CRITICAL.value == "CRITICAL"

    def test_ordering(self) -> None:
        levels = [Severity.INFO, Severity.LOW, Severity.MEDIUM, Severity.HIGH, Severity.CRITICAL]
        assert len(levels) == 5
        assert levels.index(Severity.CRITICAL) > levels.index(Severity.INFO)


class TestFindingStatus:
    def test_values(self) -> None:
        assert FindingStatus.OPEN.value == "OPEN"
        assert FindingStatus.CONFIRMED.value == "CONFIRMED"
        assert FindingStatus.REMEDIATED.value == "REMEDIATED"
        assert FindingStatus.FALSE_POSITIVE.value == "FALSE_POSITIVE"
        assert FindingStatus.ACCEPTED_RISK.value == "ACCEPTED_RISK"


class TestFindingCreate:
    def test_minimal(self) -> None:
        data = FindingCreate(engagement_id=1, title="Test", category="WIFI-PSK")
        assert data.engagement_id == 1
        assert data.title == "Test"
        assert data.category == "WIFI-PSK"
        assert data.severity == Severity.INFO
        assert data.confidence is None

    def test_full(self) -> None:
        data = FindingCreate(
            engagement_id=1,
            title="Contraseña WPA2 recuperable",
            category="WIFI-PSK",
            rule_id="WIFI-PSK-001",
            severity=Severity.CRITICAL,
            confidence=1.0,
            description="La contraseña ha sido recuperada",
            impact="Acceso no autorizado a la red",
            evidence={"password": "encrypted"},
            remediation="Cambiar la contraseña",
            affected_assets=["AA:BB:CC:DD:EE:FF"],
        )
        assert data.rule_id == "WIFI-PSK-001"
        assert data.severity == Severity.CRITICAL
        assert data.confidence == 1.0
        assert len(data.affected_assets) == 1
        assert data.evidence["password"] == "encrypted"

    def test_engagement_id_validation(self) -> None:
        with pytest.raises(ValidationError):
            FindingCreate(engagement_id=0, title="Test", category="WIFI-PSK")

    def test_title_required(self) -> None:
        with pytest.raises(ValidationError):
            FindingCreate(engagement_id=1, title="", category="WIFI-PSK")


class TestFindingUpdate:
    def test_all_optional(self) -> None:
        data = FindingUpdate()
        assert data.title is None
        assert data.severity is None
        assert data.status is None

    def test_partial_update(self) -> None:
        data = FindingUpdate(status=FindingStatus.CONFIRMED, confidence=0.95)
        assert data.status == FindingStatus.CONFIRMED
        assert data.confidence == 0.95
        assert data.title is None

    def test_severity_update(self) -> None:
        data = FindingUpdate(severity=Severity.CRITICAL)
        assert data.severity == Severity.CRITICAL


class TestFindingRead:
    def test_from_attributes(self) -> None:
        """Verifica que model_validate funciona con dict."""
        data = FindingRead(
            id=1,
            engagement_id=1,
            title="Test finding",
            category="WIFI-PSK",
            severity="HIGH",
            status="OPEN",
        )
        assert data.id == 1
        assert data.title == "Test finding"
        assert data.severity == "HIGH"
        assert data.evidence == {}


class TestFindingRule:
    def test_minimal(self) -> None:
        rule = FindingRule(
            rule_id="TEST-001",
            title="Test rule",
            category="WIFI-PSK",
            severity=Severity.HIGH,
            description="A test rule",
            impact="Test impact",
            remediation="Test remediation",
        )
        assert rule.rule_id == "TEST-001"
        assert rule.confidence == 0.9  # default

    def test_with_conditions(self) -> None:
        rule = FindingRule(
            rule_id="TEST-002",
            title="Test with conditions",
            category="WIFI-WPS",
            severity=Severity.MEDIUM,
            description="Desc",
            impact="Impact",
            remediation="Fix it",
            conditions=["network.wps.enabled == true"],
            confidence=0.75,
        )
        assert len(rule.conditions) == 1
        assert rule.confidence == 0.75


class TestEngineResult:
    def test_defaults(self) -> None:
        result = EngineResult()
        assert result.total_findings == 0
        assert result.new_findings == 0
        assert result.findings == []
        assert result.errors == []

    def test_with_data(self) -> None:
        result = EngineResult(
            total_findings=3,
            new_findings=2,
            findings=[FindingRead(id=1, engagement_id=1, title="T", category="C", severity="INFO", status="OPEN")],
        )
        assert result.total_findings == 3
        assert result.new_findings == 2
        assert len(result.findings) == 1

    def test_with_errors(self) -> None:
        result = EngineResult(errors=["Error 1", "Error 2"])
        assert len(result.errors) == 2


class TestFindingSummary:
    def test_defaults(self) -> None:
        summary = FindingSummary(engagement_id=1)
        assert summary.engagement_id == 1
        assert summary.total == 0
        assert summary.by_severity == {}
        assert summary.open_critical == 0

    def test_with_counts(self) -> None:
        summary = FindingSummary(
            engagement_id=1,
            total=5,
            by_severity={"CRITICAL": 2, "HIGH": 1, "MEDIUM": 1, "INFO": 1},
            open_critical=2,
            open_high=1,
        )
        assert summary.total == 5
        assert summary.by_severity["CRITICAL"] == 2
        assert summary.open_critical == 2


# ===================================================================
# Tests del motor de hallazgos
# ===================================================================


class TestFindingsEngine:
    """Prueba el motor de hallazgos y sus reglas integradas."""

    def test_engine_initialization(self) -> None:
        engine = FindingsEngine()
        assert len(engine.rules) >= 5  # built-in rules

    def test_builtin_rules_present(self) -> None:
        engine = FindingsEngine()
        rule_ids = [r.rule_id for r in engine.rules]
        assert "WIFI-PSK-001" in rule_ids
        assert "WIFI-PSK-002" in rule_ids
        assert "WIFI-PSK-003" in rule_ids
        assert "WIFI-WPS-001" in rule_ids
        assert "WIFI-PMF-001" in rule_ids
        assert "WIFI-PMF-002" in rule_ids

    def test_builtin_rule_severities(self) -> None:
        engine = FindingsEngine()

        psk001 = engine.get_rule("WIFI-PSK-001")
        assert psk001 is not None
        assert psk001.severity == Severity.CRITICAL

        wps001 = engine.get_rule("WIFI-WPS-001")
        assert wps001 is not None
        assert wps001.severity == Severity.HIGH

        pmf001 = engine.get_rule("WIFI-PMF-001")
        assert pmf001 is not None
        assert pmf001.severity == Severity.MEDIUM

    def test_get_rule_not_found(self) -> None:
        engine = FindingsEngine()
        assert engine.get_rule("NONEXISTENT") is None

    # ------------------------------------------------------------------
    # Register custom rules
    # ------------------------------------------------------------------

    def test_register_custom_rule(self) -> None:
        engine = FindingsEngine()
        custom = FindingRule(
            rule_id="CUSTOM-001",
            title="Custom rule",
            category="CUSTOM",
            severity=Severity.LOW,
            description="A custom rule",
            impact="Low impact",
            remediation="Easy fix",
        )
        engine.register_rule(custom)
        assert engine.get_rule("CUSTOM-001") is custom

    def test_register_replaces_existing(self) -> None:
        engine = FindingsEngine()
        updated = FindingRule(
            rule_id="WIFI-PSK-001",
            title="Updated title",
            category="WIFI-PSK",
            severity=Severity.MEDIUM,  # changed
            description="Updated",
            impact="Impact",
            remediation="Remediation",
        )
        engine.register_rule(updated)
        rule = engine.get_rule("WIFI-PSK-001")
        assert rule is not None
        assert rule.title == "Updated title"
        assert rule.severity == Severity.MEDIUM

    def test_custom_rules_on_init(self) -> None:
        custom = FindingRule(
            rule_id="INIT-001",
            title="Init rule",
            category="CUSTOM",
            severity=Severity.INFO,
            description="Added at init",
            impact="Impact",
            remediation="Remediation",
        )
        engine = FindingsEngine(custom_rules=[custom])
        assert engine.get_rule("INIT-001") is not None

    # ------------------------------------------------------------------
    # Evaluación de condiciones
    # ------------------------------------------------------------------

    def test_check_wps_enabled_true(self) -> None:
        engine = FindingsEngine()
        context = {"wps": {"enabled": True, "pin": True}}
        assert engine._check_wps_enabled(None, context) is True

    def test_check_wps_enabled_false(self) -> None:
        engine = FindingsEngine()
        context = {"wps": {"enabled": False}}
        assert engine._check_wps_enabled(None, context) is False

    def test_check_wps_enabled_missing(self) -> None:
        engine = FindingsEngine()
        assert engine._check_wps_enabled(None, {}) is False

    def test_check_wps_pin_true(self) -> None:
        engine = FindingsEngine()
        context = {"wps": {"pin": True}}
        assert engine._check_wps_pin(None, context) is True

    def test_check_wps_pin_false(self) -> None:
        engine = FindingsEngine()
        context = {"wps": {"pin": False}}
        assert engine._check_wps_pin(None, context) is False

    def test_check_pmf_optional(self) -> None:
        engine = FindingsEngine()
        context = {"pmf": {"status": "optional"}}
        assert engine._check_pmf(None, context, "optional") is True

    def test_check_pmf_not_supported(self) -> None:
        engine = FindingsEngine()
        context = {"pmf": {"status": "not_supported"}}
        assert engine._check_pmf(None, context, "not_supported") is True

    def test_check_pmf_wrong_value(self) -> None:
        engine = FindingsEngine()
        context = {"pmf": {"status": "required"}}
        assert engine._check_pmf(None, context, "optional") is False

    def test_check_context_condition_true(self) -> None:
        engine = FindingsEngine()
        context = {"data": {"ssid": "TestNet"}}
        assert engine._check_context_condition('data.ssid == "TestNet"', context) is True

    def test_check_context_condition_false(self) -> None:
        engine = FindingsEngine()
        context = {"data": {"ssid": "OtherNet"}}
        assert engine._check_context_condition('data.ssid == "TestNet"', context) is False

    def test_check_context_condition_missing_key(self) -> None:
        engine = FindingsEngine()
        assert engine._check_context_condition("data.nonexistent == true", {}) is False

    def test_check_context_condition_no_operator(self) -> None:
        engine = FindingsEngine()
        assert engine._check_context_condition("invalid_format", {}) is False

    def test_check_context_condition_wrong_prefix(self) -> None:
        engine = FindingsEngine()
        assert engine._check_context_condition("other.key == value", {}) is False

    # ------------------------------------------------------------------
    # WPS conditions
    # ------------------------------------------------------------------

    def test_evaluate_rule_wps_true(self) -> None:
        engine = FindingsEngine()
        rule = FindingRule(
            rule_id="TEST-WPS",
            title="WPS enabled",
            category="WIFI-WPS",
            severity=Severity.HIGH,
            description="WPS hazard",
            impact="Impact",
            remediation="Fix",
            conditions=["network.wps.enabled == true", "network.wps.pin == true"],
        )
        context = {"wps": {"enabled": True, "pin": True}}
        result = engine._evaluate_rule(rule, None, None, context)
        assert result is True

    def test_evaluate_rule_wps_false(self) -> None:
        engine = FindingsEngine()
        rule = FindingRule(
            rule_id="TEST-WPS",
            title="WPS enabled",
            category="WIFI-WPS",
            severity=Severity.HIGH,
            description="WPS hazard",
            impact="Impact",
            remediation="Fix",
            conditions=["network.wps.enabled == true"],
        )
        context = {"wps": {"enabled": False}}
        result = engine._evaluate_rule(rule, None, None, context)
        assert result is False

    def test_evaluate_rule_pmf_true(self) -> None:
        engine = FindingsEngine()
        rule = FindingRule(
            rule_id="TEST-PMF",
            title="PMF optional",
            category="WIFI-PMF",
            severity=Severity.MEDIUM,
            description="PMF",
            impact="Impact",
            remediation="Fix",
            conditions=["network.pmf == optional"],
        )
        context = {"pmf": {"status": "optional"}}
        result = engine._evaluate_rule(rule, None, None, context)
        assert result is True

    # ------------------------------------------------------------------
    # CRUD con base de datos
    # ------------------------------------------------------------------

    def test_create_finding(self, db_session) -> None:
        """Crea un engagement y después un hallazgo."""
        eng = Engagement(
            code="ENG-TEST-001",
            name="Test Engagement",
            client="Test Client",
            operator="Test Operator",
            status="ACTIVE",
        )
        db_session.add(eng)
        db_session.commit()

        engine = FindingsEngine()
        data = FindingCreate(
            engagement_id=eng.id,
            title="Test Finding",
            category="WIFI-PSK",
            severity=Severity.HIGH,
            description="A test finding",
            confidence=0.9,
        )
        result = engine.create_finding(db_session, data)
        assert result.id > 0
        assert result.title == "Test Finding"
        assert result.severity == "HIGH"
        assert result.confidence == 0.9
        assert result.status == "OPEN"

    def test_get_finding_not_found(self, db_session) -> None:
        engine = FindingsEngine()
        result = engine.get_finding(db_session, 9999)
        assert result is None

    def test_list_findings(self, db_session) -> None:
        """Crear engagement + hallazgos y listarlos."""
        eng = Engagement(
            code="ENG-TEST-002",
            name="List Test",
            client="Client",
            operator="Operator",
            status="ACTIVE",
        )
        db_session.add(eng)
        db_session.commit()

        engine = FindingsEngine()
        for sev in [Severity.HIGH, Severity.MEDIUM, Severity.INFO]:
            data = FindingCreate(
                engagement_id=eng.id,
                title=f"Finding {sev.value}",
                category="WIFI-PSK",
                severity=sev,
            )
            engine.create_finding(db_session, data)

        all_findings = engine.list_findings(db_session, engagement_id=eng.id)
        assert len(all_findings) == 3

        # Filter by severity.
        high_findings = engine.list_findings(db_session, severity="HIGH")
        assert len(high_findings) >= 1
        assert all(f.severity == "HIGH" for f in high_findings)

    def test_list_findings_empty(self, db_session) -> None:
        engine = FindingsEngine()
        results = engine.list_findings(db_session, engagement_id=999)
        assert results == []

    def test_update_finding(self, db_session) -> None:
        eng = Engagement(
            code="ENG-UPDATE",
            name="Update Test",
            client="Client",
            operator="Operator",
            status="ACTIVE",
        )
        db_session.add(eng)
        db_session.commit()

        engine = FindingsEngine()
        data = FindingCreate(
            engagement_id=eng.id,
            title="Original",
            category="WIFI-PSK",
        )
        created = engine.create_finding(db_session, data)

        updated = engine.update_finding(
            db_session, created.id,
            {"title": "Updated", "severity": "CRITICAL", "status": "CONFIRMED"},
        )
        assert updated is not None
        assert updated.title == "Updated"
        assert updated.severity == "CRITICAL"
        assert updated.status == "CONFIRMED"

    def test_update_finding_not_found(self, db_session) -> None:
        engine = FindingsEngine()
        result = engine.update_finding(db_session, 9999, {"title": "Nope"})
        assert result is None

    def test_delete_finding(self, db_session) -> None:
        eng = Engagement(
            code="ENG-DELETE",
            name="Delete Test",
            client="Client",
            operator="Operator",
            status="ACTIVE",
        )
        db_session.add(eng)
        db_session.commit()

        engine = FindingsEngine()
        data = FindingCreate(engagement_id=eng.id, title="To delete", category="WIFI-PSK")
        created = engine.create_finding(db_session, data)

        assert engine.delete_finding(db_session, created.id) is True
        assert engine.get_finding(db_session, created.id) is None

    def test_delete_finding_not_found(self, db_session) -> None:
        engine = FindingsEngine()
        assert engine.delete_finding(db_session, 9999) is False

    # ------------------------------------------------------------------
    # Resumen
    # ------------------------------------------------------------------

    def test_get_summary(self, db_session) -> None:
        eng = Engagement(
            code="ENG-SUMMARY",
            name="Summary Test",
            client="Client",
            operator="Operator",
            status="ACTIVE",
        )
        db_session.add(eng)
        db_session.commit()

        engine = FindingsEngine()
        for sev in [Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.INFO]:
            engine.create_finding(
                db_session,
                FindingCreate(engagement_id=eng.id, title=f"F-{sev.value}", category="WIFI-PSK", severity=sev),
            )

        summary = engine.get_summary(db_session, eng.id)
        assert summary.total == 4
        assert summary.by_severity.get("CRITICAL") == 1
        assert summary.by_severity.get("HIGH") == 1
        assert summary.by_severity.get("MEDIUM") == 1
        assert summary.by_severity.get("INFO") == 1
        assert summary.open_critical == 1
        assert summary.open_high == 1

    def test_get_summary_empty(self, db_session) -> None:
        engine = FindingsEngine()
        summary = engine.get_summary(db_session, 9999)
        assert summary.total == 0
        assert summary.by_severity == {}

    # ------------------------------------------------------------------
    # has_existing_finding
    # ------------------------------------------------------------------

    def test_has_existing_finding_true(self, db_session) -> None:
        eng = Engagement(
            code="ENG-EXIST",
            name="Existing Test",
            client="Client",
            operator="Operator",
            status="ACTIVE",
        )
        db_session.add(eng)
        db_session.commit()

        finding = Finding(
            engagement_id=eng.id,
            title="Existing",
            category="WIFI-PSK",
            rule_id="WIFI-PSK-001",
            severity="CRITICAL",
            status="OPEN",
        )
        db_session.add(finding)
        db_session.commit()

        engine = FindingsEngine()
        assert engine._has_existing_finding("WIFI-PSK-001", eng.id, db_session) is True

    def test_has_existing_finding_false(self, db_session) -> None:
        engine = FindingsEngine()
        assert engine._has_existing_finding("WIFI-PSK-001", 999, db_session) is False

    # ------------------------------------------------------------------
    # Validación de handshake
    # ------------------------------------------------------------------

    def test_has_validated_handshake_false(self, db_session) -> None:
        """Sin HandshakeArtifacts validados, retorna False."""
        engine = FindingsEngine()
        eng = Engagement(
            code="ENG-HS",
            name="HS Test",
            client="C",
            operator="O",
            status="ACTIVE",
        )
        db_session.add(eng)
        db_session.commit()
        assert engine._has_validated_handshake(eng, db_session) is False

    # ------------------------------------------------------------------
    # Cracking status checks
    # ------------------------------------------------------------------

    def test_has_recovered_password_false(self, db_session) -> None:
        """Sin CrackingJobs recoverados, retorna False."""
        engine = FindingsEngine()
        eng = Engagement(
            code="ENG-CRACK",
            name="Crack Test",
            client="C",
            operator="O",
            status="ACTIVE",
        )
        db_session.add(eng)
        db_session.commit()
        assert engine._has_recovered_password(eng, db_session) is False

    def test_has_exhausted_cracking_false(self, db_session) -> None:
        """Sin CrackingJobs exhaustos, retorna False."""
        engine = FindingsEngine()
        eng = Engagement(
            code="ENG-EXH",
            name="Exh Test",
            client="C",
            operator="O",
            status="ACTIVE",
        )
        db_session.add(eng)
        db_session.commit()
        assert engine._has_exhausted_cracking(eng, db_session) is False

    # ------------------------------------------------------------------
    # Motor completo - todas las reglas
    # ------------------------------------------------------------------

    def test_run_for_engagement_with_context(self, db_session) -> None:
        """Ejecuta el motor con contexto WPS."""
        eng = Engagement(
            code="ENG-MOTOR",
            name="Motor Test",
            client="Client",
            operator="Operator",
            status="ACTIVE",
        )
        db_session.add(eng)
        db_session.commit()

        engine = FindingsEngine()
        context = {
            "wps": {"enabled": True, "pin": True},
            "pmf": {"status": "optional"},
        }
        result = engine.run_for_engagement(eng, db_session, context)

        # WIFI-WPS-001 debería activarse con el contexto WPS.
        # WIFI-PMF-001 también debería activarse.
        wps_findings = [f for f in result.findings if f.rule_id == "WIFI-WPS-001"]
        pmf_findings = [f for f in result.findings if f.rule_id == "WIFI-PMF-001"]

        assert len(wps_findings) >= 1
        assert len(pmf_findings) >= 1

    def test_run_for_engagement_empty_context(self, db_session) -> None:
        """Sin contexto, solo se activan reglas basadas en BD."""
        eng = Engagement(
            code="ENG-EMPTY",
            name="Empty Test",
            client="Client",
            operator="Operator",
            status="ACTIVE",
        )
        db_session.add(eng)
        db_session.commit()

        engine = FindingsEngine()
        result = engine.run_for_engagement(eng, db_session)
        assert result.total_findings >= 0  # Sin condiciones BD, tal vez 0
        assert result.errors == []

    def test_run_all_multiple_engagements(self, db_session) -> None:
        """Ejecuta sobre todos los engagements."""
        for i in range(3):
            eng = Engagement(
                code=f"ENG-ALL-{i}",
                name=f"All Test {i}",
                client="Client",
                operator="Operator",
                status="ACTIVE",
            )
            db_session.add(eng)
        db_session.commit()

        engine = FindingsEngine()
        context = {
            "wps": {"enabled": True, "pin": True},
            "pmf": {"status": "optional"},
        }
        result = engine.run_all(db_session, context)
        assert result.total_findings >= 0
        assert result.errors == []

    # ------------------------------------------------------------------
    # Duplicados (no generar hallazgos duplicados)
    # ------------------------------------------------------------------

    def test_no_duplicate_findings(self, db_session) -> None:
        """Ejecutar el motor dos veces no debe duplicar hallazgos."""
        eng = Engagement(
            code="ENG-DUP",
            name="Dup Test",
            client="Client",
            operator="Operator",
            status="ACTIVE",
        )
        db_session.add(eng)
        db_session.commit()

        engine = FindingsEngine()
        context = {
            "wps": {"enabled": True, "pin": True},
            "pmf": {"status": "optional"},
        }

        first = engine.run_for_engagement(eng, db_session, context)
        second = engine.run_for_engagement(eng, db_session, context)

        # Segundo intento debe detectar duplicados y no crearlos.
        assert second.new_findings == 0

    # ------------------------------------------------------------------
    # Error handling
    # ------------------------------------------------------------------

    def test_rule_evaluation_error_does_not_block(self, db_session) -> None:
        """Un error en una regla no debe impedir que las demás se evalúen."""
        eng = Engagement(
            code="ENG-ERR",
            name="Err Test",
            client="Client",
            operator="Operator",
            status="ACTIVE",
        )
        db_session.add(eng)
        db_session.commit()

        engine = FindingsEngine()

        # Registrar regla que causará error.
        broken_rule = FindingRule(
            rule_id="BROKEN",
            title="Broken",
            category="WIFI-PSK",
            severity=Severity.INFO,
            description="Will fail",
            impact="None",
            remediation="None",
            conditions=["nonexistent == true"],
        )
        engine.register_rule(broken_rule)

        # Aún debe ejecutarse sin excepción.
        result = engine.run_for_engagement(eng, db_session, {"wps": {"enabled": True}})
        assert result.total_findings >= 0

    # ------------------------------------------------------------------
    # Singleton
    # ------------------------------------------------------------------

    def test_get_findings_engine_singleton(self) -> None:
        a = get_findings_engine()
        b = get_findings_engine()
        assert a is b
        assert isinstance(a, FindingsEngine)
