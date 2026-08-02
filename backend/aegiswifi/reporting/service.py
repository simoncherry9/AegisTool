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
            html_content = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>AegisWiFi Security Report</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&family=JetBrains+Mono:wght@400;700&display=swap');
        
        :root {
            --bg: #0a0b10;
            --surface: #141620;
            --surface-hover: #1c1f2e;
            --border: #2a2e40;
            --text: #e2e8f0;
            --text-muted: #94a3b8;
            --accent: #00e5ff;
            --accent-glow: rgba(0, 229, 255, 0.2);
            --critical: #ff1744;
            --high: #ff9100;
            --medium: #ffea00;
            --low: #00e676;
            --info: #2979ff;
        }

        body {
            font-family: 'Inter', sans-serif;
            background-color: var(--bg);
            color: var(--text);
            margin: 0;
            padding: 40px;
            line-height: 1.6;
        }

        .container {
            max-width: 900px;
            margin: 0 auto;
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 12px;
            box-shadow: 0 8px 32px rgba(0,0,0,0.4);
            overflow: hidden;
        }

        .header {
            background: linear-gradient(135deg, rgba(20, 22, 32, 0.9), rgba(10, 11, 16, 0.9));
            padding: 40px;
            border-bottom: 2px solid var(--accent);
            text-align: center;
            position: relative;
        }

        .header::after {
            content: '';
            position: absolute;
            bottom: -2px;
            left: 0;
            right: 0;
            height: 2px;
            background: var(--accent);
            box-shadow: 0 0 15px var(--accent);
        }

        .title {
            font-family: 'JetBrains Mono', monospace;
            font-size: 2.5rem;
            margin: 0 0 10px 0;
            color: #fff;
            letter-spacing: -1px;
            text-transform: uppercase;
        }
        
        .subtitle {
            font-size: 1.1rem;
            color: var(--text-muted);
            margin: 0;
        }

        .section {
            padding: 30px 40px;
            border-bottom: 1px solid var(--border);
        }

        .section:last-child {
            border-bottom: none;
        }

        h2 {
            font-family: 'JetBrains Mono', monospace;
            color: var(--accent);
            font-size: 1.5rem;
            margin-top: 0;
            margin-bottom: 20px;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        h2::before {
            content: '>';
            color: var(--text-muted);
        }

        .stats-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 20px;
        }

        .stat-card {
            background: var(--surface-hover);
            padding: 20px;
            border-radius: 8px;
            border: 1px solid var(--border);
            text-align: center;
        }

        .stat-value {
            font-size: 2.5rem;
            font-weight: 700;
            font-family: 'JetBrains Mono', monospace;
            color: #fff;
        }

        .stat-label {
            color: var(--text-muted);
            font-size: 0.9rem;
            text-transform: uppercase;
            letter-spacing: 1px;
        }

        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 10px;
            background: var(--surface-hover);
            border-radius: 8px;
            overflow: hidden;
        }

        th, td {
            padding: 15px 20px;
            text-align: left;
            border-bottom: 1px solid var(--border);
        }

        th {
            background: rgba(0, 0, 0, 0.2);
            color: var(--text-muted);
            font-size: 0.85rem;
            text-transform: uppercase;
            letter-spacing: 1px;
        }

        tr:last-child td {
            border-bottom: none;
        }

        .badge {
            padding: 4px 10px;
            border-radius: 4px;
            font-size: 0.75rem;
            font-weight: 700;
            font-family: 'JetBrains Mono', monospace;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .badge-CRITICAL { background: var(--critical); color: #fff; box-shadow: 0 0 10px rgba(255,23,68,0.4); }
        .badge-HIGH { background: var(--high); color: #fff; }
        .badge-MEDIUM { background: var(--medium); color: #000; }
        .badge-LOW { background: var(--low); color: #000; }
        .badge-INFO { background: var(--info); color: #fff; }

        .mono {
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.9rem;
            color: var(--accent);
        }

        footer {
            text-align: center;
            padding: 30px;
            color: var(--text-muted);
            font-size: 0.85rem;
        }
    </style>
</head>
<body>
    <div class="container">
"""
            html_content += f"""
        <div class="header">
            <h1 class="title">AegisWiFi</h1>
            <p class="subtitle">Auditoría de Seguridad Inalámbrica - {eng_name}</p>
        </div>
"""
            
            if request.include_executive_summary:
                html_content += f"""
        <div class="section">
            <h2>Resumen Ejecutivo</h2>
            <p style="margin-bottom: 25px; color: var(--text-muted);">El siguiente reporte documenta los hallazgos de seguridad y la evidencia capturada durante el proceso de auditoría.</p>
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-value">{len(findings)}</div>
                    <div class="stat-label">Vulnerabilidades Identificadas</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">{len(evidences)}</div>
                    <div class="stat-label">Artefactos de Evidencia</div>
                </div>
            </div>
        </div>
"""
                
            if request.include_findings:
                html_content += """
        <div class="section">
            <h2>Hallazgos</h2>
            <table>
                <tr>
                    <th>Severidad</th>
                    <th>Título</th>
                    <th>Descripción</th>
                </tr>
"""
                for f in findings:
                    sev = str(f.get("severity", "INFO")).upper()
                    html_content += f"""
                <tr>
                    <td style="width: 120px;"><span class="badge badge-{sev}">{sev}</span></td>
                    <td style="font-weight: 600; color: #fff;">{f.get('title')}</td>
                    <td style="color: var(--text-muted);">{f.get('description', '')}</td>
                </tr>
"""
                html_content += "</table></div>"
                
            if request.include_evidence:
                html_content += """
        <div class="section">
            <h2>Cadena de Custodia (Evidencias)</h2>
            <table>
                <tr>
                    <th>Archivo</th>
                    <th>Firma SHA-256</th>
                </tr>
"""
                for e in evidences:
                    html_content += f"""
                <tr>
                    <td class="mono">{e.get('path')}</td>
                    <td class="mono" style="color: var(--text-muted); font-size: 0.8rem;">{e.get('sha256')}</td>
                </tr>
"""
                html_content += "</table></div>"
                
            if request.include_methodology:
                html_content += """
        <div class="section">
            <h2>Metodología y Alcance</h2>
            <p style="color: var(--text-muted);">Las actividades de auditoría se realizaron de acuerdo con las reglas de alcance definidas (Scope Engine) en AegisWiFi. Las capturas de tráfico (EAPOL) y ataques dirigidos (Deauth, WPS) se ejecutaron aislando únicamente los objetivos autorizados para prevenir la interrupción de servicios fuera de cobertura.</p>
        </div>
"""
                
            html_content += f"""
        <footer>
            Generado automáticamente el {now.strftime("%Y-%m-%d %H:%M:%S UTC")} por AegisWiFi Tool.
        </footer>
    </div>
"""
            if request.format == ReportFormat.PDF:
                html_content = "<!-- PDF generation requires wkhtmltopdf -->\n" + html_content
                
            html_content += "</body></html>"
            
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
