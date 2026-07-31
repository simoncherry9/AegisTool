"""Schemas del módulo de validación de handshakes (minuta §15, §16, §28).

Define los tipos de datos para solicitudes de validación, resultados y
reportes de handshakes EAPOL/PMKID.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class QualityClassification(str, Enum):
    """Clasificación de calidad de un handshake.

    Sigue la misma semántica que :class:`HandshakeQuality <aegiswifi.database.models.HandshakeQuality>`.
    """

    EXCELLENT = "EXCELLENT"
    GOOD = "GOOD"
    ACCEPTABLE = "ACCEPTABLE"
    POOR = "POOR"
    INVALID = "INVALID"


class ValidationRequest(BaseModel):
    """Solicitud de validación de un handshake.

    Puede referenciar una captura existente por ID o proporcionar una
    ruta directa al archivo.
    """

    capture_id: int | None = None
    """ID de la captura en la BD (opcional si se provee ``file_path``)."""

    file_path: str | None = None
    """Ruta directa al archivo .pcapng (opcional si se provee ``capture_id``)."""

    engagement_id: int | None = Field(default=None, ge=1)
    """ID del engagement para asociar el artifact resultante."""

    force_reprocess: bool = False
    """Si ``True``, reprocesa aunque ya exista un artifact validado."""


class EapolAnalysis(BaseModel):
    """Análisis de los mensajes EAPOL detectados."""

    messages_found: list[str] = Field(default_factory=list)
    """Mensajes EAPOL detectados (ej. ``M1``, ``M2``, ``M3``, ``M4``)."""

    pairs_complete: list[str] = Field(default_factory=list)
    """Pares completos detectados (ej. ``M1M2``, ``M3M4``)."""

    has_full_handshake: bool = False
    """Indica si se detectó un handshake completo (M1+M2+M3+M4 o M1+M2+M3)."""

    has_m12: bool = False
    """Par M1+M2 presente (suficiente para cracking)."""

    has_m14: bool = False
    """Par M1+M4 presente."""


class PmkidAnalysis(BaseModel):
    """Análisis de PMKID detectado."""

    detected: bool = False
    """Indica si se encontró un PMKID válido."""

    raw_value: str | None = None
    """Valor crudo del PMKID (truncado)."""

    hash_line: str | None = None
    """Primeros 80 caracteres de la línea de hash 22000 generada."""


class ValidationResult(BaseModel):
    """Resultado completo de la validación de un handshake."""

    artifact_id: int | None = None
    """ID del HandshakeArtifact creado/actualizado en la BD."""

    capture_id: int | None = None
    """ID de la captura procesada."""

    quality: QualityClassification = QualityClassification.INVALID
    """Clasificación de calidad final."""

    quality_score: float = 0.0
    """Puntaje numérico 0..1 que respalda la clasificación."""

    validated: bool = False
    """Indica si el handshake superó la validación."""

    hash22000_path: str | None = None
    """Ruta al archivo .22000 generado."""

    hash22000_line: str | None = None
    """Primera línea del archivo .22000 (truncada a 80 chars)."""

    eapol: EapolAnalysis = Field(default_factory=EapolAnalysis)
    """Análisis de mensajes EAPOL."""

    pmkid: PmkidAnalysis = Field(default_factory=PmkidAnalysis)
    """Análisis de PMKID."""

    kind: str = "eapol"
    """Tipo de handshake (``eapol`` o ``pmkid``)."""

    message_pair: str | None = None
    """Mejor par de mensajes encontrado (ej. ``M1M2``)."""

    warnings: list[str] = Field(default_factory=list)
    """Advertencias durante la validación."""

    errors: list[str] = Field(default_factory=list)
    """Errores durante la validación."""

    tool_output: str | None = None
    """Salida cruda de hcxpcapngtool (truncada, útil para diagnóstico)."""

    source_file: str | None = None
    """Archivo fuente procesado."""

    processed_at: datetime = Field(default_factory=lambda: datetime.now())
    """Momento de la validación."""


class HandshakeReport(BaseModel):
    """Reporte legible de un handshake validado, para la API."""

    id: int
    """ID del HandshakeArtifact."""

    bssid: str | None = None
    """BSSID del AP."""

    ssid: str | None = None
    """SSID de la red."""

    channel: int | None = None
    """Canal de la red."""

    kind: str = "eapol"
    """Tipo de handshake."""

    quality: str = "INVALID"
    """Calidad del handshake."""

    validated: bool = False
    """Si pasó la validación."""

    message_pair: str | None = None
    """Pares EAPOL encontrados."""

    hash_file: str | None = None
    """Ruta al archivo .22000."""

    crack_status: str | None = None
    """Estado del cracking asociado (si existe)."""

    access_point_id: int | None = None
    """ID del AccessPoint asociado."""

    station_mac: str | None = None
    """MAC de la estación."""

    created_at: datetime | None = None
    """Momento de creación del artifact."""
