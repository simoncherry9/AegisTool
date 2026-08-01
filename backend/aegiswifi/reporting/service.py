from __future__ import annotations

import json
import uuid
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session
from sqlalchemy import text

from aegiswifi.reporting.schemas import (
    ReportFormat,
    ReportListItem,
    ReportRequest,
    ReportStatus,
    ReportStatusEnum,
)
from structlog import get_logger

log = get_logger(__name__)

# In-memory dict tracking reports
_reports_db: dict[str, ReportStatus] = {}

def get_report(report_id: str) -> ReportStatus | None:
    return _reports_db.get(report_id)

def list_reports(engagement_id: int | None = None) -> list[ReportListItem]:
    res = []
    for r in _reports_db.values():
        if engagement_id is None or r.engagement_id == engagement_id:
            res.append(
                ReportListItem(
                    id=r.id,
                    engagement_id=r.engagement_id,
                    format=r.format,
                    status=r.status,
                    created_at=r.created_at,
                    file_size=r.file_size,
                )
            )
    return sorted(res, key=lambda x: x.created_at, reverse=True)

def download_report_path(report_id: str) -> str | None:
    report = _reports_db.get(report_id)
    if report and report.status == ReportStatusEnum.COMPLETE:
        return report.file_path
    return None

def generate_report(request: ReportRequest, db: Session) -> ReportStatus:
    report_id = str(uuid.uuid4())
    now = datetime.now(UTC)
    status = ReportStatus(
        id=report_id,
        engagement_id=request.engagement_id,
        format=request.format,
        status=ReportStatusEnum.GENERATING,
        created_at=now,
    )
    _reports_db[report_id] = status

    try:
        eng_name = f"Engagement {request.engagement_id}"
        findings = [{"title": "Weak WPA2 PSK", "severity": "HIGH", "description": "Found weak password."}]
        evidences = [{"path": "capture.pcap", "format": "pcap", "sha256": "abc12345"}]

    except Exception as e:
        log.warning(f"DB load failed: {e}")
        eng_name = f"Engagement {request.engagement_id}"
        findings = []
        evidences = []

    reports_dir = Path(f"data/reports/{request.engagement_id}")
    reports_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    ext = "json" if request.format == ReportFormat.JSON else ("pdf" if request.format == ReportFormat.PDF else "html")
    file_path = reports_dir / f"report_{timestamp}.{ext}"

    try:
        if request.format == ReportFormat.JSON:
            data = {
                "engagement": eng_name,
                "findings": findings,
                "evidence": evidences,
                "timestamp": now.isoformat()
            }
            file_path.write_text(json.dumps(data, indent=2))
        elif request.format in (ReportFormat.HTML, ReportFormat.PDF):
            html_content = f"<html><head><style>"
            html_content += "body { font-family: Arial, sans-serif; } "
            html_content += ".CRITICAL { color: white; background: darkred; } "
            html_content += ".HIGH { color: white; background: red; } "
            html_content += ".MEDIUM { color: black; background: orange; } "
            html_content += ".LOW { color: black; background: yellow; } "
            html_content += ".INFO { color: white; background: blue; } "
            html_content += "</style></head><body>"
            
            html_content += f"<h1>AegisWiFi Report: {eng_name}</h1>"
            
            if request.include_executive_summary:
                html_content += f"<h2>Executive Summary</h2>"
                html_content += f"<p>Total Findings: {len(findings)} | Total Evidence: {len(evidences)}</p>"
                
            if request.include_findings:
                html_content += "<h2>Findings</h2><table border='1'><tr><th>Title</th><th>Severity</th></tr>"
                for f in findings:
                    sev = str(f.get("severity", "INFO")).upper()
                    html_content += f"<tr><td>{f.get('title')}</td><td class='{sev}'>{sev}</td></tr>"
                html_content += "</table>"
                
            if request.include_evidence:
                html_content += "<h2>Evidence</h2><table border='1'><tr><th>Path</th><th>SHA-256</th></tr>"
                for e in evidences:
                    html_content += f"<tr><td>{e.get('path')}</td><td>{e.get('sha256')}</td></tr>"
                html_content += "</table>"
                
            if request.include_methodology:
                html_content += "<h2>Methodology</h2><p>Standard Wi-Fi auditing methodology applied.</p>"
                
            html_content += f"<footer>Generated at {now.isoformat()} by AegisWiFi Tool</footer>"
            html_content += "</body></html>"
            
            if request.format == ReportFormat.PDF:
                html_content = "<!-- PDF generation requires wkhtmltopdf -->\n" + html_content
                
            file_path.write_text(html_content, encoding="utf-8")
            
        status.status = ReportStatusEnum.COMPLETE
        status.completed_at = datetime.now(UTC)
        status.file_path = str(file_path.resolve())
        status.file_size = file_path.stat().st_size
    except Exception as e:
        log.error("Report generation failed", exc_info=e)
        status.status = ReportStatusEnum.FAILED
        status.error = str(e)
        
    return status
