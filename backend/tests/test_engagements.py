"""Tests unitarios del servicio de engagements + schemas (minuta §2, §11, §28)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from aegiswifi.database.models import Engagement, EngagementStatus
from aegiswifi.engagements.schemas import EngagementCreate, EngagementRead, EngagementUpdate
from aegiswifi.engagements.service import (
    activate,
    assert_active_and_not_expired,
    close,
    create_engagement,
    generate_code,
    get_engagement,
    is_expired,
    list_engagements,
    update_engagement,
)


# ===================================================================
# Helpers
# ===================================================================


def _eng(session: Session, code: str = "ENG-TEST-001") -> Engagement:
    eng = Engagement(
        name="test",
        client="client",
        operator="op",
        status=EngagementStatus.DRAFT,
        code=code,
        permissions={},
        limits={},
    )
    session.add(eng)
    session.commit()
    session.refresh(eng)
    return eng


# ===================================================================
# Code Generation Tests
# ===================================================================


class TestGenerateCode:
    def test_generates_first_code(self, db_session: Session):
        """Sin engagements previos, genera ENG-YYYY-001."""
        code = generate_code(db_session)
        assert code.startswith("ENG-")
        assert code.endswith("-001")
        year = datetime.now(UTC).year
        assert str(year) in code

    def test_generates_sequential_codes(self, db_session: Session):
        """Con engagements existentes, el contador avanza."""
        c1 = generate_code(db_session)
        _eng(db_session, code=c1)  # crear un engagement con ese código

        c2 = generate_code(db_session)
        assert c2.endswith("-002")

    def test_code_handles_gaps(self, db_session: Session):
        """Si existe -001 y -003, genera -004 (toma el max+1)."""
        year = datetime.now(UTC).year
        eng1 = _eng(db_session, f"ENG-{year}-001")
        eng2 = _eng(db_session, f"ENG-{year}-003")
        code = generate_code(db_session)
        assert code.endswith("-004")


# ===================================================================
# Engagement CRUD Tests
# ===================================================================


class TestCreateEngagement:
    def test_creates_with_defaults(self, db_session: Session):
        payload = EngagementCreate(name="Test", client="Client", operator="Operator")
        eng = create_engagement(db_session, payload)
        assert eng.id is not None
        assert eng.name == "Test"
        assert eng.client == "Client"
        assert eng.operator == "Operator"
        assert eng.status == EngagementStatus.DRAFT.value
        assert eng.code is not None
        assert eng.permissions == {}
        assert eng.limits == {}

    def test_creates_with_optional_fields(self, db_session: Session):
        now = datetime.now(UTC)
        payload = EngagementCreate(
            name="Advanced",
            client="Big Client",
            operator="Expert",
            start_date=now,
            end_date=now + timedelta(hours=8),
            authorization_reference="AUTH-001",
            notes="Test engagement",
            permissions={"handshake_capture": True},
            limits={"max_frames": 4},
        )
        eng = create_engagement(db_session, payload)
        assert eng.start_date is not None
        assert eng.authorization_reference == "AUTH-001"
        assert eng.notes == "Test engagement"
        assert eng.permissions == {"handshake_capture": True}

    def test_rejects_empty_name(self):
        with pytest.raises(Exception):
            EngagementCreate(name="", client="Client", operator="Operator")


class TestListEngagements:
    def test_list_all(self, db_session: Session):
        _eng(db_session, "LIST-001")
        _eng(db_session, "LIST-002")
        engagements = list_engagements(db_session)
        assert len(engagements) >= 2

    def test_list_empty(self, db_session: Session):
        engagements = list_engagements(db_session)
        assert engagements == []


class TestGetEngagement:
    def test_get_by_id(self, db_session: Session):
        eng = _eng(db_session, "GET-001")
        found = get_engagement(db_session, eng.id)
        assert found is not None
        assert found.id == eng.id

    def test_get_not_found(self, db_session: Session):
        from aegiswifi.core.exceptions import NotFound

        with pytest.raises(NotFound):
            get_engagement(db_session, 9999)


class TestUpdateEngagement:
    def test_update_status(self, db_session: Session):
        eng = _eng(db_session, "UPD-001")
        updated = update_engagement(
            db_session, eng.id, EngagementUpdate(status=EngagementStatus.READY)
        )
        assert updated.status == EngagementStatus.READY.value

    def test_update_notes(self, db_session: Session):
        eng = _eng(db_session, "UPD-002")
        updated = update_engagement(db_session, eng.id, EngagementUpdate(notes="New notes"))
        assert updated.notes == "New notes"


# ===================================================================
# Activation / Close Tests
# ===================================================================


class TestActivate:
    def test_activate_draft(self, db_session: Session):
        eng = _eng(db_session, "ACT-001")
        activated = activate(db_session, eng.id)
        assert activated.status == EngagementStatus.ACTIVE.value

    def test_activate_already_active(self, db_session: Session):
        eng = _eng(db_session, "ACT-002")
        eng.status = EngagementStatus.ACTIVE.value
        db_session.commit()
        # Activar un engagement ya activo es no-op.
        activated = activate(db_session, eng.id)
        assert activated.status == EngagementStatus.ACTIVE.value

    def test_activate_completed_raises(self, db_session: Session):
        from aegiswifi.core.exceptions import Conflict

        eng = _eng(db_session, "ACT-003")
        eng.status = EngagementStatus.COMPLETED.value
        db_session.commit()
        with pytest.raises(Conflict, match="COMPLETED"):
            activate(db_session, eng.id)


class TestClose:
    def test_close_active(self, db_session: Session):
        eng = _eng(db_session, "CLS-001")
        close(db_session, eng.id)
        db_session.refresh(eng)
        assert eng.status == EngagementStatus.COMPLETED.value

    def test_close_active_sets_completed(self, db_session: Session):
        eng = _eng(db_session, "CLS-002")
        eng.status = EngagementStatus.ACTIVE.value
        db_session.commit()
        close(db_session, eng.id)
        db_session.refresh(eng)
        assert eng.status == EngagementStatus.COMPLETED.value

    def test_close_draft(self, db_session: Session):
        """Cerrar un draft es válido."""
        eng = _eng(db_session, "CLS-003")
        close(db_session, eng.id)
        db_session.refresh(eng)
        assert eng.status == EngagementStatus.COMPLETED.value


# ===================================================================
# Expiry Tests
# ===================================================================


class TestExpiry:
    def test_is_expired_true(self, db_session: Session):
        eng = _eng(db_session, "EXP-001")
        eng.end_date = datetime.now(UTC) - timedelta(hours=1)
        assert is_expired(eng) is True

    def test_is_expired_false(self, db_session: Session):
        eng = _eng(db_session, "EXP-002")
        eng.end_date = datetime.now(UTC) + timedelta(hours=1)
        assert is_expired(eng) is False

    def test_is_expired_no_end_date(self, db_session: Session):
        eng = _eng(db_session, "EXP-003")
        eng.end_date = None
        assert is_expired(eng) is False

    def test_assert_active_and_not_expired_ok(self, db_session: Session):
        eng = _eng(db_session, "EXP-004")
        eng.status = EngagementStatus.ACTIVE.value
        eng.end_date = datetime.now(UTC) + timedelta(hours=1)
        # No debe lanzar.
        assert_active_and_not_expired(eng)

    def test_assert_active_not_active(self, db_session: Session):
        from aegiswifi.core.exceptions import ValidationFailed

        eng = _eng(db_session, "EXP-005")
        eng.status = EngagementStatus.DRAFT.value
        with pytest.raises(ValidationFailed):
            assert_active_and_not_expired(eng)

    def test_assert_active_expired(self, db_session: Session):
        from aegiswifi.core.exceptions import ScopeViolation

        eng = _eng(db_session, "EXP-006")
        eng.status = EngagementStatus.ACTIVE.value
        eng.end_date = datetime.now(UTC) - timedelta(hours=1)
        with pytest.raises(ScopeViolation):
            assert_active_and_not_expired(eng)


# ===================================================================
# Schema Tests
# ===================================================================


class TestEngagementSchemas:
    def test_engagement_create_requires_name(self):
        with pytest.raises(Exception):
            EngagementCreate(name="", client="c", operator="o")

    def test_engagement_create_requires_client(self):
        with pytest.raises(Exception):
            EngagementCreate(name="n", client="", operator="o")

    def test_engagement_create_requires_operator(self):
        with pytest.raises(Exception):
            EngagementCreate(name="n", client="c", operator="")

    def test_engagement_create_minimal(self):
        payload = EngagementCreate(name="Test", client="Client", operator="Operator")
        data = payload.model_dump()
        assert data["name"] == "Test"
        assert data["permissions"] == {}
        assert data["start_date"] is None

    def test_engagement_read_from_attributes(self, db_session: Session):
        eng = _eng(db_session, "SCH-001")
        read = EngagementRead.model_validate(eng)
        assert read.id == eng.id
        assert read.code == "SCH-001"
        assert read.status == EngagementStatus.DRAFT

    def test_engagement_update_partial(self):
        update = EngagementUpdate(notes="Only notes changed")
        data = update.model_dump(exclude_unset=True)
        assert "notes" in data
        assert "name" not in data

    def test_engagement_update_status(self):
        update = EngagementUpdate(status=EngagementStatus.READY)
        data = update.model_dump(exclude_unset=True)
        assert data["status"] == EngagementStatus.READY
