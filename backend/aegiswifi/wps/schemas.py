"""DTOs del módulo WPS."""

from __future__ import annotations

import enum
from datetime import datetime

from pydantic import BaseModel, Field


class WpsMethod(str, enum.Enum):
    PIXIE_DUST = "pixie_dust"
    BRUTE_FORCE = "brute_force"
    BULLY = "bully"


class WpsAttackStatusEnum(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    STOPPED = "stopped"


class WpsScanRequest(BaseModel):
    interface: str = Field(..., description="Interfaz en modo monitor")


class WpsScanResult(BaseModel):
    bssid: str
    ssid: str | None = None
    channel: int | None = None
    wps_version: str = "1.0"
    wps_locked: bool = False
    signal: int | None = None


class WpsAttackRequest(BaseModel):
    interface: str = Field(..., description="Interfaz en modo monitor")
    bssid: str = Field(..., description="BSSID del AP objetivo")
    channel: int | None = Field(None, ge=1, le=196)
    method: WpsMethod = Field(WpsMethod.PIXIE_DUST, description="Método de ataque")
    timeout: int = Field(300, ge=30, le=3600)


class WpsAttackStatusRead(BaseModel):
    id: str
    status: WpsAttackStatusEnum
    interface: str
    bssid: str
    method: WpsMethod
    started_at: datetime | None = None
    elapsed_seconds: int = 0
    pin_found: str | None = None
    psk_found: str | None = None
    progress_pct: float = 0.0
    error: str | None = None
