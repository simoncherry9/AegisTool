"""Generación de informes a partir de datos persistidos (minuta §33–§35)."""

from __future__ import annotations

import html
import json
import shutil
import subprocess
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from aegiswifi.core.config import get_settings
from aegiswifi.database.models import Capture, Engagement, Finding
from aegiswifi.reporting.schemas import (
    ReportFormat,
    ReportListItem,
    ReportRequest,
    ReportStatus,
    ReportStatusEnum,
)

_reports_db: dict[str, ReportStatus] = {}


def get_report(report_id: str) -> ReportStatus | None:
    return _reports_db.get(report_id)


def list_reports(engagement_id: int | None = None) -> list[ReportListItem]:
    reports = (
        report
        for report in _reports_db.values()
        if engagement_id is None or report.engagement_id == engagement_id
    )
    return sorted(
        (ReportListItem.model_validate(report.model_dump()) for report in reports),
        key=lambda report: report.created_at,
        reverse=True,
    )


def download_report_path(report_id: str) -> str | None:
    report = _reports_db.get(report_id)
    if report is None or report.status != ReportStatusEnum.COMPLETE or not report.file_path:
        return None
    path = Path(report.file_path)
    return str(path) if path.is_file() else None


def _report_data(request: ReportRequest, db: Session, created_at: datetime) -> dict[str, Any]:
    engagement = db.get(Engagement, request.engagement_id)
    if engagement is None:
        raise ValueError(f"engagement {request.engagement_id} no encontrado")

    findings = list(
        db.scalars(
            select(Finding)
            .where(Finding.engagement_id == request.engagement_id)
            .order_by(Finding.severity, Finding.id)
        ).all()
    )
    evidence = list(
        db.scalars(
            select(Capture)
            .where(Capture.engagement_id == request.engagement_id)
            .order_by(Capture.created_at)
        ).all()
    )
    return {
        "generated_at": created_at.isoformat(),
        "engagement": {
            "id": engagement.id,
            "code": engagement.code,
            "name": engagement.name,
            "client": engagement.client,
            "operator": engagement.operator,
            "status": str(engagement.status),
            "authorization_reference": engagement.authorization_reference,
        },
        "findings": [
            {
                "id": finding.id,
                "title": finding.title,
                "category": finding.category,
                "severity": str(finding.severity),
                "status": str(finding.status),
                "description": finding.description,
                "impact": finding.impact,
                "remediation": finding.remediation,
                "affected_assets": finding.affected_assets,
            }
            for finding in findings
        ],
        "evidence": [
            {
                "id": capture.id,
                "filename": capture.original_filename,
                "category": capture.category,
                "format": capture.format,
                "sha256": capture.sha256,
                "tool": capture.tool,
                "tool_version": capture.tool_version,
                "created_at": capture.created_at.isoformat(),
            }
            for capture in evidence
        ],
    }


def _render_html(data: dict[str, Any], request: ReportRequest) -> str:
    engagement = cast(dict[str, object], data["engagement"])
    findings = cast(list[dict[str, object]], data["findings"]) if request.include_findings else []
    evidence = cast(list[dict[str, object]], data["evidence"]) if request.include_evidence else []

    def esc(value: object) -> str:
        return html.escape(str(value or "—"))

    finding_rows = (
        "".join(
            f"<tr><td><span class='severity {esc(item['severity']).lower()}'>{esc(item['severity'])}</span></td>"
            f"<td><strong>{esc(item['title'])}</strong><small>{esc(item['category'])}</small></td>"
            f"<td>{esc(item['description'])}</td><td>{esc(item['remediation'])}</td></tr>"
            for item in findings
        )
        or "<tr><td colspan='4' class='empty'>No se registraron hallazgos.</td></tr>"
    )
    evidence_rows = (
        "".join(
            f"<tr><td>{esc(item['filename'])}</td><td>{esc(item['format'])}</td>"
            f"<td class='mono'>{esc(item['sha256'])}</td><td>{esc(item['tool'])}</td></tr>"
            for item in evidence
        )
        or "<tr><td colspan='4' class='empty'>No se registró evidencia.</td></tr>"
    )

    return f"""<!doctype html><html lang='es'><head><meta charset='utf-8'>
<title>Informe {esc(engagement["code"])}</title><style>
@page {{ margin: 22mm; }} body {{ font: 14px Arial,sans-serif; color:#17202a; margin:40px; }}
header {{ border-bottom:3px solid #177e75; padding-bottom:24px; margin-bottom:32px; }}
.brand {{ color:#177e75; font-size:13px; font-weight:bold; letter-spacing:2px; text-transform:uppercase; }}
h1 {{ font-size:30px; margin:8px 0; }} h2 {{ margin-top:32px; font-size:19px; }}
.meta {{ color:#657383; }} .summary {{ display:flex; gap:16px; margin:24px 0; }}
.metric {{ border:1px solid #dfe5ea; border-radius:8px; padding:16px 22px; }}
.metric strong {{ display:block; font-size:24px; }} table {{ width:100%; border-collapse:collapse; }}
th,td {{ padding:10px; border-bottom:1px solid #e3e8ec; text-align:left; vertical-align:top; }}
th {{ color:#657383; font-size:11px; text-transform:uppercase; }} small {{ display:block; color:#718096; margin-top:3px; }}
.mono {{ font:11px Consolas,monospace; word-break:break-all; }} .severity {{ font-weight:bold; font-size:11px; }}
.severity.critical,.severity.high {{ color:#b42318; }} .severity.medium {{ color:#946200; }} .empty {{ color:#718096; text-align:center; }}
footer {{ margin-top:40px; padding-top:16px; border-top:1px solid #dfe5ea; color:#718096; font-size:11px; }}
</style></head><body><header><div class='brand'>AegisWiFi · Informe de auditoría</div>
<h1>{esc(engagement["name"])}</h1><div class='meta'>{esc(engagement["code"])} · {esc(engagement["client"])} · Operador: {esc(engagement["operator"])}</div></header>
<section><h2>Resumen ejecutivo</h2><p>Este documento consolida los resultados y la cadena de custodia del engagement autorizado.</p>
<div class='summary'><div class='metric'><strong>{len(findings)}</strong>Hallazgos</div><div class='metric'><strong>{len(evidence)}</strong>Evidencias</div></div></section>
<section><h2>Hallazgos</h2><table><thead><tr><th>Severidad</th><th>Hallazgo</th><th>Descripción</th><th>Remediación</th></tr></thead><tbody>{finding_rows}</tbody></table></section>
<section><h2>Cadena de custodia</h2><table><thead><tr><th>Archivo</th><th>Formato</th><th>SHA-256</th><th>Herramienta</th></tr></thead><tbody>{evidence_rows}</tbody></table></section>
<footer>Generado {esc(data["generated_at"])}. Las credenciales recuperadas se omiten deliberadamente.</footer></body></html>"""


def generate_report(request: ReportRequest, db: Session) -> ReportStatus:
    report_id = str(uuid.uuid4())
    now = datetime.now(UTC)
    report = ReportStatus(
        id=report_id,
        engagement_id=request.engagement_id,
        format=request.format,
        status=ReportStatusEnum.GENERATING,
        created_at=now,
    )
    _reports_db[report_id] = report
    reports_dir = get_settings().paths.data_dir / "reports" / str(request.engagement_id)
    reports_dir.mkdir(parents=True, exist_ok=True)

    try:
        data = _report_data(request, db, now)
        base_path = reports_dir / f"report_{now:%Y%m%d_%H%M%S}_{report_id[:8]}"
        if request.format == ReportFormat.JSON:
            file_path = base_path.with_suffix(".json")
            file_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        else:
            html_content = _render_html(data, request)
            if request.format == ReportFormat.HTML:
                file_path = base_path.with_suffix(".html")
                file_path.write_text(html_content, encoding="utf-8")
            else:
                converter = shutil.which("wkhtmltopdf")
                if converter is None:
                    raise RuntimeError(
                        "wkhtmltopdf no está instalado; genera HTML o instala el conversor PDF"
                    )
                source_path = base_path.with_suffix(".html")
                file_path = base_path.with_suffix(".pdf")
                source_path.write_text(html_content, encoding="utf-8")
                result = subprocess.run(
                    [converter, "--quiet", str(source_path), str(file_path)],
                    capture_output=True,
                    text=True,
                    timeout=120,
                    check=False,
                )
                if result.returncode != 0:
                    raise RuntimeError(result.stderr.strip() or "no se pudo generar el PDF")

        report.status = ReportStatusEnum.COMPLETE
        report.completed_at = datetime.now(UTC)
        report.file_path = str(file_path.resolve())
        report.file_size = file_path.stat().st_size
    except Exception as exc:
        report.status = ReportStatusEnum.FAILED
        report.completed_at = datetime.now(UTC)
        report.error = str(exc)
    return report
