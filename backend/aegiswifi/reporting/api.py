from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from aegiswifi.database.engine import get_db
from aegiswifi.reporting.schemas import ReportListItem, ReportRequest, ReportStatus
from aegiswifi.reporting import service as reporting_service

router = APIRouter(prefix="/reports", tags=["reports"])

@router.post("/generate", response_model=ReportStatus)
def generate_report(request: ReportRequest, db: Session = Depends(get_db)):
    return reporting_service.generate_report(request, db)

@router.get("", response_model=list[ReportListItem])
def list_reports(engagement_id: int | None = None):
    return reporting_service.list_reports(engagement_id)

@router.get("/{report_id}", response_model=ReportStatus)
def get_report(report_id: str):
    report = reporting_service.get_report(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report

@router.get("/{report_id}/download")
def download_report(report_id: str):
    path = reporting_service.download_report_path(report_id)
    if not path:
        raise HTTPException(status_code=404, detail="Report file not found or not complete")
    return FileResponse(path)
