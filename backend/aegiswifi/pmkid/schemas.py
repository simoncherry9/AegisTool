"""DTOs del módulo de captura PMKID (minuta §16, §17)."""

from __future__ import annotations

import enum
from datetime import datetime

from pydantic import BaseModel, Field


class PMKIDCaptureStatus(str, enum.Enum):
    PENDING = "pending"
    CAPTURING = "capturing"
    COMPLETE = "complete"
    FAILED = "failed"
    STOPPED = "stopped"


class PMKIDCaptureRequest(BaseModel):
    interface: str = Field(..., description="Interfaz en modo monitor")
    bssid: str | None = Field(None, description="BSSID objetivo (opcional)")
    channel: int | None = Field(None, ge=1, le=196, description="Canal específico")
    duration: int = Field(60, ge=10, le=300, description="Duración en segundos")


class PMKIDCaptureStatusRead(BaseModel):
    id: str
    status: PMKIDCaptureStatus
    interface: str
    bssid: str | None = None
    started_at: datetime | None = None
    elapsed_seconds: int = 0
    pmkid_count: int = 0
    pcap_path: str | None = None
    hash_path: str | None = None
    error: str | None = None
