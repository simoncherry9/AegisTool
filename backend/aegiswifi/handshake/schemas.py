"""DTOs del módulo de captura de handshake EAPOL (minuta §15, §17)."""

from __future__ import annotations

import enum
from datetime import datetime

from pydantic import BaseModel, Field


class CaptureStatus(str, enum.Enum):
    """Estado de una captura de handshake."""

    PENDING = "pending"
    CAPTURING = "capturing"
    VALIDATING = "validating"
    CONVERTING = "converting"
    COMPLETE = "complete"
    FAILED = "failed"
    STOPPED = "stopped"


class HandshakeCaptureRequest(BaseModel):
    """Solicitud para iniciar captura dirigida de handshake EAPOL."""

    interface: str = Field(..., description="Interfaz en modo monitor")
    bssid: str = Field(..., description="BSSID del AP objetivo")
    channel: int | None = Field(None, ge=1, le=196, description="Canal del AP")
    duration: int = Field(120, ge=10, le=600, description="Duración máxima en segundos")
    deauth_assisted: bool = Field(
        False, description="Enviar deauth limitada para forzar reconexión"
    )
    deauth_count: int = Field(3, ge=1, le=20, description="Cantidad de paquetes deauth")


class HandshakeCaptureStatusRead(BaseModel):
    """Estado actual de una captura de handshake."""

    id: str
    status: CaptureStatus
    interface: str
    bssid: str
    channel: int | None = None
    started_at: datetime | None = None
    elapsed_seconds: int = 0
    handshake_detected: bool = False
    pcap_path: str | None = None
    hash_path: str | None = None
    artifact_id: int | None = None
    error: str | None = None


class HandshakeCaptureResult(BaseModel):
    """Resultado final de la captura."""

    success: bool
    handshake_valid: bool = False
    hash_file: str | None = None
    evidence_id: int | None = None
