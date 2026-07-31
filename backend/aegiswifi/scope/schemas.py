"""DTOs del alcance y la autorización (minuta §12).

Estructura del archivo YAML de alcance (minuta §12.2) con validación estricta:
los permisos son booleanos, los límites numéricos y no negativos.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator


class EngagementHeader(BaseModel):
    """Cabecera de autorización del archivo de alcance (minuta §12)."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., min_length=1)
    client: str = Field(..., min_length=1)
    operator: str = Field(..., min_length=1)
    valid_from: datetime
    valid_until: datetime

    @field_validator("valid_until")
    @classmethod
    def _valid_after(cls, v: datetime, info: ValidationInfo) -> datetime:
        v_from = info.data.get("valid_from")
        if v_from and v < v_from:
            raise ValueError("valid_until debe ser posterior a valid_from")
        return v


class ScopeBlock(BaseModel):
    """Bloque ``scope`` del archivo (minuta §12)."""

    model_config = ConfigDict(extra="forbid")

    allowed_ssids: list[str] = Field(default_factory=list)
    allowed_bssids: list[str] = Field(default_factory=list)
    allowed_clients: list[str] = Field(default_factory=list)
    channels: list[int] = Field(default_factory=list)
    bands: list[str] = Field(default_factory=list)

    @field_validator("bands")
    @classmethod
    def _band_values(cls, v: list[str]) -> list[str]:
        for b in v:
            if b not in {"2.4", "5", "6"}:
                raise ValueError(f"banda no reconocida: {b}")
        return v


class Permissions(BaseModel):
    """Permisos accionables que el PolicyEngine consultará (minuta §12)."""

    model_config = ConfigDict(extra="forbid")

    passive_capture: bool = False
    handshake_capture: bool = False
    pmkid_capture: bool = False
    controlled_reconnect: bool = False
    password_audit: bool = False
    wps_testing: bool = False
    enterprise_testing: bool = False
    denial_of_service: bool = False
    protocol_fuzzing: bool = False


class Limits(BaseModel):
    """Límites cuantitativos de cada engagement (minuta §12)."""

    model_config = ConfigDict(extra="forbid")

    maximum_active_frames: int = Field(default=4, ge=0)
    maximum_cracking_duration_minutes: int = Field(default=120, ge=0)
    maximum_gpu_temperature: int = Field(default=78, ge=0)


class ScopeFile(BaseModel):
    """Estructura raíz del archivo de alcance importable (minuta §12)."""

    model_config = ConfigDict(extra="forbid")

    engagement: EngagementHeader
    scope: ScopeBlock
    permissions: Permissions
    limits: Limits
