"""DTOs Pydantic del módulo de evidencia (minuta §30)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CaptureRead(BaseModel):
    """DTO completo de una captura/evidencia."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    engagement_id: int
    job_id: int | None = None
    category: str = "original"
    path: str
    format: str = "pcapng"
    sha256: str | None = None
    original_filename: str | None = None
    size_bytes: int | None = None
    interface: str | None = None
    channel: int | None = None
    bssid: str | None = None
    ssid: str | None = None
    tool: str | None = None
    tool_version: str | None = None
    metadata: dict[str, Any] = Field(default={}, validation_alias="extra_metadata")
    derived_from_id: int | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime


class CaptureListRead(BaseModel):
    """Versión ligera de Capture para listados."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    engagement_id: int
    job_id: int | None = None
    category: str
    format: str
    sha256: str | None = None
    original_filename: str | None = None
    size_bytes: int | None = None
    tool: str | None = None
    created_at: datetime


class EvidenceStoreResponse(BaseModel):
    """Respuesta después de almacenar evidencia."""

    capture_id: int
    path: str
    sha256: str
    size_bytes: int
    category: str
    format: str
