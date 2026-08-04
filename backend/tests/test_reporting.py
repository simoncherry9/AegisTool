"""Pruebas del generador de informes con datos persistidos (minuta §33–§35)."""

from __future__ import annotations

import json
from pathlib import Path

from aegiswifi.database.models import Capture, Engagement, EngagementStatus, Finding, Severity
from aegiswifi.reporting.schemas import ReportFormat, ReportRequest, ReportStatusEnum
from aegiswifi.reporting.service import generate_report


def _engagement(db_session) -> Engagement:
    engagement = Engagement(
        code="ENG-REPORT-001",
        name="Auditoría <principal>",
        client="Cliente de prueba",
        operator="Operador",
        status=EngagementStatus.ACTIVE,
    )
    db_session.add(engagement)
    db_session.commit()
    db_session.refresh(engagement)
    return engagement


def test_json_report_uses_database_records(db_session, monkeypatch, tmp_path):
    engagement = _engagement(db_session)
    db_session.add(
        Finding(
            engagement_id=engagement.id,
            title="PMF no requerido",
            category="WIFI-PMF",
            severity=Severity.MEDIUM,
            description="Configuración observada",
        )
    )
    db_session.add(
        Capture(
            engagement_id=engagement.id,
            path=str(tmp_path / "capture.pcapng"),
            original_filename="capture.pcapng",
            format="pcapng",
            sha256="a" * 64,
            tool="airodump-ng",
        )
    )
    db_session.commit()
    monkeypatch.setattr(
        "aegiswifi.reporting.service.get_settings",
        lambda: type("Settings", (), {"paths": type("Paths", (), {"data_dir": tmp_path})()})(),
    )

    report = generate_report(
        ReportRequest(engagement_id=engagement.id, format=ReportFormat.JSON), db_session
    )

    assert report.status == ReportStatusEnum.COMPLETE
    payload = json.loads(Path(report.file_path or "").read_text(encoding="utf-8"))
    assert payload["engagement"]["code"] == engagement.code
    assert payload["findings"][0]["title"] == "PMF no requerido"
    assert payload["evidence"][0]["sha256"] == "a" * 64


def test_html_report_escapes_stored_text(db_session, monkeypatch, tmp_path):
    engagement = _engagement(db_session)
    monkeypatch.setattr(
        "aegiswifi.reporting.service.get_settings",
        lambda: type("Settings", (), {"paths": type("Paths", (), {"data_dir": tmp_path})()})(),
    )

    report = generate_report(
        ReportRequest(engagement_id=engagement.id, format=ReportFormat.HTML), db_session
    )

    content = Path(report.file_path or "").read_text(encoding="utf-8")
    assert "Auditoría &lt;principal&gt;" in content
    assert "Auditoría <principal>" not in content


def test_missing_engagement_fails_without_fabricating_data(db_session):
    report = generate_report(
        ReportRequest(engagement_id=999_999, format=ReportFormat.JSON), db_session
    )

    assert report.status == ReportStatusEnum.FAILED
    assert "no encontrado" in (report.error or "")
    assert report.file_path is None
