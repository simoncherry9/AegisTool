"""Schemas del motor de hallazgos (minuta §29, §28).

Define los tipos de datos para hallazgos, reglas de detección y
resultados del motor de análisis.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class Severity(str, Enum):
    """Severidad de un hallazgo (minuta §28)."""

    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class FindingStatus(str, Enum):
    """Estados del ciclo de vida de un hallazgo (minuta §28)."""

    OPEN = "OPEN"
    CONFIRMED = "CONFIRMED"
    REMEDIATED = "REMEDIATED"
    FALSE_POSITIVE = "FALSE_POSITIVE"
    ACCEPTED_RISK = "ACCEPTED_RISK"


class FindingCreate(BaseModel):
    """Datos para crear un nuevo hallazgo."""

    engagement_id: int = Field(..., ge=1)
    """ID del engagement al que pertenece el hallazgo."""

    title: str = Field(..., min_length=1, max_length=255)
    """Título descriptivo del hallazgo."""

    category: str = Field(..., max_length=64)
    """Categoría (ej. WIFI-PSK, WIFI-WPS, WIFI-PMF, WIFI-ENTERPRISE)."""

    rule_id: str | None = Field(default=None, max_length=64)
    """ID de la regla que detectó el hallazgo (ej. WIFI-PSK-001)."""

    severity: Severity = Severity.INFO
    """Severidad del hallazgo."""

    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    """Confianza en el hallazgo (0..1)."""

    description: str | None = Field(default=None, max_length=2000)
    """Descripción detallada del hallazgo."""

    impact: str | None = Field(default=None, max_length=2000)
    """Impacto potencial del hallazgo."""

    evidence: dict[str, Any] = Field(default_factory=dict)
    """Evidencias que respaldan el hallazgo (ej. rutas de archivos, hashes)."""

    remediation: str | None = Field(default=None, max_length=2000)
    """Recomendación de remediación."""

    affected_assets: list[str] = Field(default_factory=list)
    """Lista de activos afectados (ej. BSSID, SSID)."""


class FindingUpdate(BaseModel):
    """Datos para actualizar un hallazgo existente."""

    title: str | None = Field(default=None, min_length=1, max_length=255)
    severity: Severity | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    description: str | None = Field(default=None, max_length=2000)
    impact: str | None = Field(default=None, max_length=2000)
    evidence: dict[str, Any] | None = None
    remediation: str | None = Field(default=None, max_length=2000)
    affected_assets: list[str] | None = None
    status: FindingStatus | None = None


class FindingRead(BaseModel):
    """Hallazgo tal como se expone en la API."""

    id: int
    engagement_id: int
    title: str
    category: str
    rule_id: str | None = None
    severity: str
    confidence: float | None = None
    description: str | None = None
    impact: str | None = None
    evidence: dict[str, Any] = {}
    remediation: str | None = None
    affected_assets: list[str] = []
    status: str
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class FindingRule(BaseModel):
    """Regla de detección de hallazgos.

    Una regla define condiciones bajo las cuales se genera un hallazgo
    profesional a partir de datos técnicos.
    """

    rule_id: str
    """Identificador único de la regla (ej. WIFI-PSK-001)."""

    title: str
    """Título del hallazgo que genera esta regla."""

    category: str
    """Categoría del hallazgo."""

    severity: Severity
    """Severidad por defecto."""

    description: str
    """Descripción del hallazgo."""

    impact: str
    """Impacto del hallazgo."""

    remediation: str
    """Recomendación de remediación."""

    conditions: list[str] = Field(default_factory=list)
    """Condiciones para activar la regla (expresiones lógicas)."""

    confidence: float = Field(default=0.9, ge=0.0, le=1.0)
    """Confianza por defecto."""


class EngineResult(BaseModel):
    """Resultado de una ejecución del motor de hallazgos."""

    total_findings: int = 0
    """Cantidad total de hallazgos generados."""

    new_findings: int = 0
    """Cantidad de hallazgos nuevos (no duplicados)."""

    findings: list[FindingRead] = Field(default_factory=list)
    """Hallazgos generados en esta ejecución."""

    errors: list[str] = Field(default_factory=list)
    """Errores durante la ejecución del motor."""


class FindingSummary(BaseModel):
    """Resumen de hallazgos para un engagement."""

    engagement_id: int
    total: int = 0
    by_severity: dict[str, int] = Field(default_factory=dict)
    by_category: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    open_critical: int = 0
    open_high: int = 0
    open_medium: int = 0
    open_low: int = 0
    open_info: int = 0
