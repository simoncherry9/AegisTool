"""Módulo de hallazgos (minuta §29, §28).

Convierte evidencia técnica en hallazgos profesionales mediante reglas
de detección configurables. Incluye CRUD para hallazgos y motor
automático de generación.
"""

from __future__ import annotations

from aegiswifi.findings.engine import FindingsEngine, get_findings_engine
from aegiswifi.findings.schemas import (
    EngineResult,
    FindingCreate,
    FindingRead,
    FindingRule,
    FindingStatus,
    FindingSummary,
    FindingUpdate,
    Severity,
)

__all__ = [
    "FindingsEngine",
    "get_findings_engine",
    "EngineResult",
    "FindingCreate",
    "FindingRead",
    "FindingUpdate",
    "FindingRule",
    "FindingRule",
    "FindingStatus",
    "FindingSummary",
    "Severity",
]
