"""DTOs del módulo de deauthentication."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class DeauthRequest(BaseModel):
    interface: str = Field(..., description="Interfaz en modo monitor")
    bssid: str = Field(..., description="BSSID objetivo")
    client_mac: str | None = Field(None, description="MAC del cliente (opcional - broadcast si es None)")
    count: int = Field(5, ge=1, le=50, description="Cantidad de paquetes deauth (máximo 50)")
    reason: str | None = Field(None, description="Motivo / auditoría")


class DeauthResult(BaseModel):
    id: str
    success: bool
    packets_sent: int
    interface: str
    bssid: str
    client_mac: str | None = None
    timestamp: datetime
    error: str | None = None
