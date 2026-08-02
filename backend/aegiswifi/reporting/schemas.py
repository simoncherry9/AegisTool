from __future__ import annotations

from datetime import datetime
from enum import Enum
import uuid

from pydantic import BaseModel


class ReportFormat(str, Enum):
    HTML = "html"
    PDF = "pdf"
    JSON = "json"


class ReportStatusEnum(str, Enum):
    PENDING = "PENDING"
    GENERATING = "GENERATING"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"


class ReportRequest(BaseModel):
    engagement_id: int
    format: ReportFormat
    include_executive_summary: bool = True
    include_findings: bool = True
    include_evidence: bool = True
    include_methodology: bool = True


class ReportStatus(BaseModel):
    id: str
    engagement_id: int
    format: ReportFormat
    status: ReportStatusEnum
    created_at: datetime
    completed_at: datetime | None = None
    file_path: str | None = None
    file_size: int | None = None
    error: str | None = None


class ReportListItem(BaseModel):
    id: str
    engagement_id: int
    format: ReportFormat
    status: ReportStatusEnum
    created_at: datetime
    file_size: int | None = None
