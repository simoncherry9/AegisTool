"""Smoke tests del health check y del ciclo de vida de un engagement."""

from __future__ import annotations

from aegiswifi.database.models import EngagementStatus


def test_health_ok(client):
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"
    assert body["version"]


def test_engagement_lifecycle(client):
    # Crear
    resp = client.post(
        "/api/v1/engagements",
        json={"name": "Lab", "client": "Cliente", "operator": "Op"},
    )
    assert resp.status_code == 201
    eng = resp.json()
    assert eng["status"] == EngagementStatus.DRAFT.value
    eng_id = eng["id"]
    assert eng["code"].startswith("ENG-")

    # Recuperar
    assert client.get(f"/api/v1/engagements/{eng_id}").json()["id"] == eng_id

    # Activar
    activated = client.post(f"/api/v1/engagements/{eng_id}/activate").json()
    assert activated["status"] == EngagementStatus.ACTIVE.value

    # Cerrar
    closed = client.post(f"/api/v1/engagements/{eng_id}/close").json()
    assert closed["status"] == EngagementStatus.COMPLETED.value


def test_engagement_not_found(client):
    resp = client.get("/api/v1/engagements/9999")
    assert resp.status_code == 404


def test_engagement_code_increments(client, db_session):
    from aegiswifi.engagements.service import generate_code

    c1 = generate_code(db_session)
    assert c1.endswith("-001")
    # Simula un engagement ya persistido con código -001.
    from aegiswifi.database.models import Engagement

    db_session.add(
        Engagement(
            code=c1, name="x", client="c", operator="o", status="DRAFT", permissions={}, limits={}
        )
    )
    db_session.commit()
    c2 = generate_code(db_session)
    assert c2.endswith("-002")
