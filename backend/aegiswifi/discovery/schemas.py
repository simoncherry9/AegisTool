"""DTOs Pydantic del módulo de descubrimiento (minuta §14, §37).

Define modelos para Access Points, clientes, escaneo, filtros,
eventos en tiempo real y exportación de inventario.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

# ── Security enums ───────────────────────────────────────────────────


class SecurityProtocol(StrEnum):
    """Protocolo de seguridad detectado en un AP."""

    OPEN = "OPEN"
    WEP = "WEP"
    WPA = "WPA"
    WPA2 = "WPA2"
    WPA3 = "WPA3"
    WPA_WPA2 = "WPA/WPA2"
    WPA2_WPA3 = "WPA2/WPA3"
    UNKNOWN = "UNKNOWN"


class AknMethod(StrEnum):
    """Authentication and Key Management (AKM) suite."""

    PSK = "PSK"
    SAE = "SAE"
    FT_PSK = "FT-PSK"
    FT_SAE = "FT-SAE"
    EAP = "EAP"
    FT_EAP = "FT-EAP"
    OWE = "OWE"
    WPS = "WPS"
    UNKNOWN = "UNKNOWN"


class CipherSuite(StrEnum):
    """Cipher suite usado para cifrado de unicast/group."""

    CCMP = "CCMP"
    GCMP = "GCMP"
    TKIP = "TKIP"
    WEP40 = "WEP-40"
    WEP104 = "WEP-104"
    UNKNOWN = "UNKNOWN"


class PnfMode(StrEnum):
    """Modo de Protected Management Frames (PMF / MFP)."""

    DISABLED = "disabled"
    OPTIONAL = "optional"
    REQUIRED = "required"
    UNKNOWN = "unknown"


class TransitionMode(StrEnum):
    """Modo de transición WPA3."""

    NONE = "None"
    WPA3_TRANSITION = "WPA3-Transition"
    WPA2_WPA3_MIXED = "WPA2/WPA3-Mixed"
    UNKNOWN = "Unknown"


class BandEnum(StrEnum):
    """Banda de frecuencia."""

    BAND_2GHZ = "2.4 GHz"
    BAND_5GHZ = "5 GHz"
    BAND_6GHZ = "6 GHz"


# ── Access Point models ──────────────────────────────────────────────


class AccessPointSummary(BaseModel):
    """Resumen de un AP para listados ligeros."""

    model_config = ConfigDict(from_attributes=True)

    bssid: str
    ssid: str | None = None
    channel: int | None = None
    frequency: int | None = None
    band: BandEnum | None = None
    signal: int | None = None
    vendor: str | None = None
    protocol: SecurityProtocol = SecurityProtocol.UNKNOWN
    in_scope: bool = False
    clients_count: int = 0
    first_seen: datetime | None = None
    last_seen: datetime | None = None


class AccessPointDetail(AccessPointSummary):
    """Detalle completo de un AP con clasificación de seguridad."""

    akm: str | None = None
    cipher: str | None = None
    pmf: PnfMode = PnfMode.UNKNOWN
    wps: bool = False
    transition_mode: TransitionMode = TransitionMode.UNKNOWN
    wpa3_supported: bool = False
    beacon_interval: int | None = None
    beacon_count: int | None = None
    capabilities: list[str] = Field(default_factory=list)
    degraded: bool = False


# ── Client models ────────────────────────────────────────────────────


class ClientSummary(BaseModel):
    """Resumen de un cliente (estación) descubierto."""

    model_config = ConfigDict(from_attributes=True)

    mac: str
    randomized: bool = False
    vendor: str | None = None
    associated_bssid: str | None = None
    associated_ssid: str | None = None
    signal: int | None = None
    probe_requests: list[str] = Field(default_factory=list)
    first_seen: datetime | None = None
    last_seen: datetime | None = None
    controlled: bool = False


# ── Scan models ──────────────────────────────────────────────────────


class ScanConfig(BaseModel):
    """Configuración para iniciar un escaneo."""

    interface: str
    channel: int | None = None
    band: BandEnum | None = None
    hop_interval: int = 1
    output_prefix: str | None = None
    duration: int | None = None


class ScanStatus(BaseModel):
    """Estado actual de un escaneo en ejecución."""

    running: bool = False
    interface: str | None = None
    channel: int | None = None
    uptime_seconds: int | None = None
    ap_count: int = 0
    client_count: int = 0
    started_at: datetime | None = None
    error: str | None = None


# ── Filters ──────────────────────────────────────────────────────────


class InventoryFilter(BaseModel):
    """Filtros para consultar el inventario."""

    ssid: str | None = None
    bssid: str | None = None
    band: BandEnum | None = None
    channel: int | None = None
    protocol: SecurityProtocol | None = None
    in_scope: bool | None = None
    wps: bool | None = None
    pmf: PnfMode | None = None
    signal_min: int | None = None
    signal_max: int | None = None
    vendor: str | None = None
    client_mac: str | None = None
    client_associated: bool | None = None
    limit: int = 100
    offset: int = 0


# ── Events (WebSocket) ──────────────────────────────────────────────


class DiscoveryEvent(BaseModel):
    """Evento emitido por WebSocket cuando el inventario cambia."""

    event_type: str
    data: dict[str, Any]
    timestamp: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())


class InventorySnapshot(BaseModel):
    """Snapshot completo del inventario actual."""

    access_points: list[AccessPointDetail] = Field(default_factory=list)
    clients: list[ClientSummary] = Field(default_factory=list)
    scan_status: ScanStatus = Field(default_factory=ScanStatus)
    timestamp: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())


# ── Export ───────────────────────────────────────────────────────────


class InventoryExport(BaseModel):
    """Exportación del inventario a JSON."""

    exported_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    engagement_id: int | None = None
    access_points: list[AccessPointDetail] = Field(default_factory=list)
    clients: list[ClientSummary] = Field(default_factory=list)
    filters_applied: InventoryFilter | None = None