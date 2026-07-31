"""DTOs Pydantic del módulo de interfaces (minuta §13, §37).

Define los modelos de datos intercambiados entre las capas de detección,
monitor, restauración/servicio y la API REST.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class WirelessInterface(BaseModel):
    """Información completa de una interfaz inalámbrica.

    Contiene todos los datos detectados por :mod:`aegiswifi.interfaces.detection`
    más las capacidades inferidas por :mod:`aegiswifi.interfaces.monitor`.
    """

    model_config = ConfigDict(from_attributes=True)

    name: str
    phy: str | None = None
    mac: str | None = None
    chipset: str | None = None
    driver: str | None = None
    driver_version: str | None = None
    bands: list[str] = Field(default_factory=list)  # ["2.4 GHz", "5 GHz"]
    channels: list[int] = Field(default_factory=list)
    supported_modes: list[str] = Field(default_factory=list)
    type: str = "managed"  # managed | monitor | AP
    state: str = "down"  # up | down
    is_physical: bool = True
    monitor_mode: bool = False
    ap_mode: bool = False
    injection_supported: bool | None = None
    blocked: bool = False
    signal: int | None = None
    noise: int | None = None


class InterfaceState(BaseModel):
    """Estado guardado de una interfaz antes de modificarla.

    Se persiste a JSON en ``data/interface_states/{iface}.json``
    por :func:`aegiswifi.interfaces.restoration.save_interface_state`.
    """

    interface: str
    original_type: str
    original_channel: int | None = None
    was_up: bool
    saved_at: datetime = Field(default_factory=datetime.now)
    original_flags: list[str] = Field(default_factory=list)


class InterfacePrepareResult(BaseModel):
    """Resultado de :func:`aegiswifi.interfaces.service.prepare_interface`."""

    interface: str
    monitor_interface: str
    mode_set: bool
    injection_ok: bool | None
    original_state: InterfaceState


class InterfaceRestoreResult(BaseModel):
    """Resultado de :func:`aegiswifi.interfaces.service.restore_interface`."""

    interface: str
    restored: bool
    current_type: str


class InterfaceDiagnostic(BaseModel):
    """Diagnóstico completo de una interfaz o del sistema."""

    interface: str | None = None
    present: bool = False
    blocked: bool = False
    conflicting_processes: list[str] = Field(default_factory=list)
    rfkill_blocks: list[dict[str, Any]] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)
