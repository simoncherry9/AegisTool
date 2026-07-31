"""Módulo de validación de handshakes (minuta §15, §16, §28).

Analiza capturas en busca de handshakes EAPOL y PMKID, clasifica su
calidad, y prepara archivos .22000 para el módulo de cracking.
"""

from __future__ import annotations

from aegiswifi.validation.schemas import (
    HandshakeReport,
    QualityClassification,
    ValidationRequest,
    ValidationResult,
)
from aegiswifi.validation.service import HandshakeValidationService, get_validation_service

__all__ = [
    "ValidationRequest",
    "ValidationResult",
    "HandshakeReport",
    "QualityClassification",
    "HandshakeValidationService",
    "get_validation_service",
]
