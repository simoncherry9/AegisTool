"""Tests del parser de alcance y del PolicyEngine (minuta §12)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from aegiswifi.core.exceptions import ScopeViolation, ValidationFailed
from aegiswifi.scope.parser import parse_scope_yaml
from aegiswifi.scope.policy import PolicyEngine, ScopeContext, Usage
from aegiswifi.scope.schemas import Limits, Permissions, ScopeBlock

VALID_YAML = """
engagement:
  id: ENG-2026-001
  client: Laboratorio autorizado
  operator: Operador principal
  valid_from: 2026-07-29T08:00:00-03:00
  valid_until: 2026-07-29T18:00:00-03:00
scope:
  allowed_ssids: [LAB-WPA2]
  allowed_bssids: [AA:BB:CC:DD:EE:FF]
permissions:
  passive_capture: true
  handshake_capture: true
  password_audit: true
  denial_of_service: false
limits:
  maximum_active_frames: 4
  maximum_cracking_duration_minutes: 120
  maximum_gpu_temperature: 78
"""


def test_parse_valid_scope():
    scope = parse_scope_yaml(VALID_YAML)
    assert scope.engagement.id == "ENG-2026-001"
    assert scope.scope.allowed_ssids == ["LAB-WPA2"]
    assert scope.permissions.handshake_capture is True
    assert scope.limits.maximum_gpu_temperature == 78


def test_parse_rejects_extra_keys():
    bad = VALID_YAML + "\nunknown_top_key: 1\n"
    with pytest.raises(ValidationFailed):
        parse_scope_yaml(bad)


def test_parse_rejects_bad_band():
    bad = VALID_YAML.replace(
        "permissions:\n",
        "scope_extra_only: true\npermissions:\n",
    )
    # Construye un YAML con una banda inválida dentro del bloque scope.
    bad = VALID_YAML.replace(
        "allowed_ssids: [LAB-WPA2]", "allowed_ssids: [LAB-WPA2]\n  bands: ['7.0']"
    )
    with pytest.raises(ValidationFailed):
        parse_scope_yaml(bad)


def test_parse_invalid_yaml():
    with pytest.raises(ValidationFailed):
        parse_scope_yaml("engagement: [this is not valid yaml: - -")


def _ctx(now: datetime | None = None, perm: Permissions | None = None) -> ScopeContext:
    now = now or datetime.now(UTC)
    return ScopeContext(
        engagement_code="ENG-2026-001",
        valid_from=now - timedelta(hours=1),
        valid_until=now + timedelta(hours=1),
        scope=ScopeBlock(allowed_ssids=["LAB"], allowed_bssids=["AA:BB:CC:DD:EE:FF"]),
        permissions=perm or Permissions(passive_capture=True, handshake_capture=True),
        limits=Limits(
            maximum_active_frames=4,
            maximum_cracking_duration_minutes=120,
            maximum_gpu_temperature=78,
        ),
        operator="Op",
    )


def test_policy_allows_in_scope():
    engine = PolicyEngine(_ctx())
    engine.assert_allowed("handshake_capture", ssid="LAB", bssid="AA:BB:CC:DD:EE:FF")


def test_policy_blocks_out_of_scope_ssid():
    engine = PolicyEngine(_ctx())
    with pytest.raises(ScopeViolation):
        engine.assert_allowed("handshake_capture", ssid="OTHER", bssid="AA:BB:CC:DD:EE:FF")


def test_policy_blocks_unpermitted_action():
    perm = Permissions(handshake_capture=False)
    engine = PolicyEngine(_ctx(perm=perm))
    with pytest.raises(ScopeViolation):
        engine.assert_allowed("handshake_capture", ssid="LAB", bssid="AA:BB:CC:DD:EE:FF")


def test_policy_blocks_expired_window():
    past = datetime.now(UTC) - timedelta(hours=10)
    ctx = ScopeContext(
        engagement_code="ENG-X",
        valid_from=past - timedelta(hours=8),
        valid_until=past,
        scope=ScopeBlock(allowed_ssids=["LAB"], allowed_bssids=["AA:BB:CC:DD:EE:FF"]),
        permissions=Permissions(handshake_capture=True),
        limits=Limits(
            maximum_active_frames=4,
            maximum_cracking_duration_minutes=120,
            maximum_gpu_temperature=78,
        ),
        operator="Op",
    )
    with pytest.raises(ScopeViolation):
        PolicyEngine(ctx).assert_allowed("handshake_capture", ssid="LAB", bssid="AA:BB:CC:DD:EE:FF")


def test_policy_frame_budget():
    ctx = _ctx()
    ctx.usage = Usage(active_frames_sent=4)
    with pytest.raises(ScopeViolation):
        PolicyEngine(ctx).assert_within_frame_budget()


def test_policy_gpu_temperature():
    ctx = _ctx()
    ctx.usage = Usage(current_gpu_temp=80)
    with pytest.raises(ScopeViolation):
        PolicyEngine(ctx).assert_gpu_temperature()


# ===================================================================
# Scope Service Tests
# ===================================================================


class TestScopeService:
    """Tests del servicio de importación de alcance (scope/service.py)."""

    def test_import_scope_creates_targets(self, db_session, tmp_path):
        """import_scope crea ScopeTarget entries desde un YAML válido."""
        from datetime import UTC, datetime, timedelta

        from aegiswifi.database.models import Engagement, EngagementStatus, ScopeTarget
        from aegiswifi.scope.service import import_scope

        now = datetime.now(UTC)
        eng = Engagement(
            name="scope-test",
            client="client",
            operator="op",
            status=EngagementStatus.DRAFT,
            code="ENG-2026-001",
            permissions={},
            limits={},
        )
        db_session.add(eng)
        db_session.commit()
        db_session.refresh(eng)

        yaml_content = f"""---
engagement:
  id: ENG-2026-001
  client: client
  operator: op
  valid_from: {now.isoformat()}
  valid_until: {(now + timedelta(hours=8)).isoformat()}
scope:
  allowed_ssids: [LAB-WIFI, GUEST-NET]
  allowed_bssids: [AA:BB:CC:DD:EE:FF, 00:11:22:33:44:55]
  allowed_clients: []
permissions:
  passive_capture: true
  handshake_capture: true
  password_audit: false
limits:
  maximum_active_frames: 4
  maximum_cracking_duration_minutes: 120
"""
        scope_file = tmp_path / "scope.yaml"
        scope_file.write_text(yaml_content, encoding="utf-8")

        engagement, scope = import_scope(db_session, eng.id, scope_file)

        assert engagement.code == "ENG-2026-001"
        assert engagement.permissions == {"passive_capture": True, "handshake_capture": True,
                                          "password_audit": False, "pmkid_capture": False,
                                          "controlled_reconnect": False, "wps_testing": False,
                                          "enterprise_testing": False, "denial_of_service": False,
                                          "protocol_fuzzing": False}
        # Verificar que se crearon los targets.
        targets = db_session.query(ScopeTarget).filter(
            ScopeTarget.engagement_id == eng.id
        ).all()
        assert len(targets) == 4  # 2 ssids + 2 bssids
        ssids = [t.ssid for t in targets if t.ssid]
        bssids = [t.bssid for t in targets if t.bssid]
        assert "LAB-WIFI" in ssids
        assert "AA:BB:CC:DD:EE:FF" in bssids

    def test_import_scope_replaces_previous_targets(self, db_session, tmp_path):
        """import_scope elimina targets previos y crea nuevos."""
        from datetime import UTC, datetime, timedelta

        from aegiswifi.database.models import Engagement, EngagementStatus, ScopeTarget
        from aegiswifi.scope.service import import_scope

        now = datetime.now(UTC)
        eng = Engagement(
            name="replace-test",
            client="c",
            operator="o",
            status=EngagementStatus.DRAFT,
            code="ENG-2026-002",
            permissions={},
            limits={},
        )
        db_session.add(eng)
        db_session.commit()
        db_session.refresh(eng)

        # Target previo.
        db_session.add(ScopeTarget(engagement_id=eng.id, ssid="OLD-SSID"))
        db_session.commit()

        yaml_content = f"""---
engagement:
  id: ENG-2026-002
  client: c
  operator: o
  valid_from: {now.isoformat()}
  valid_until: {(now + timedelta(hours=8)).isoformat()}
scope:
  allowed_ssids: [NEW-SSID]
  allowed_bssids: []
permissions:
  passive_capture: true
limits:
  maximum_active_frames: 4
"""
        scope_file = tmp_path / "scope_replace.yaml"
        scope_file.write_text(yaml_content, encoding="utf-8")

        import_scope(db_session, eng.id, scope_file)

        targets = db_session.query(ScopeTarget).filter(
            ScopeTarget.engagement_id == eng.id
        ).all()
        assert len(targets) == 1
        assert targets[0].ssid == "NEW-SSID"
        assert "OLD-SSID" not in [t.ssid for t in targets]

    def test_import_scope_rejects_wrong_code(self, db_session, tmp_path):
        """import_scope rechaza si el id del archivo no coincide."""
        from aegiswifi.core.exceptions import ValidationFailed
        from aegiswifi.database.models import Engagement, EngagementStatus
        from aegiswifi.scope.service import import_scope

        eng = Engagement(
            name="code-test",
            client="c",
            operator="o",
            status=EngagementStatus.DRAFT,
            code="ENG-9999-XXX",
            permissions={},
            limits={},
        )
        db_session.add(eng)
        db_session.commit()
        db_session.refresh(eng)

        yaml_content = """---
engagement:
  id: DIFFERENT-CODE
  client: c
  operator: o
  valid_from: 2026-07-29T08:00:00Z
  valid_until: 2026-07-29T18:00:00Z
scope:
  allowed_ssids: []
  allowed_bssids: []
permissions:
  passive_capture: true
limits:
  maximum_active_frames: 4
"""
        scope_file = tmp_path / "scope_bad.yaml"
        scope_file.write_text(yaml_content, encoding="utf-8")

        with pytest.raises(ValidationFailed, match="no coincide"):
            import_scope(db_session, eng.id, scope_file)
