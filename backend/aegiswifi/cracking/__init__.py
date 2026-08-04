"""Módulo de auditoría de contraseñas con Hashcat (minuta §18, §28).

Expone:
  - :class:`HashcatAdapter` — adaptador ToolAdapter para hashcat.
  - :class:`DictionaryManager` — gestión de diccionarios/wordlists.
  - :class:`RulesManager` — gestión de reglas de hashcat.
  - :class:`CrackingPlanner` — planificador multi-etapa.
  - :func:`get_cracking_service` — singleton del servicio de cracking.
"""

from __future__ import annotations

from aegiswifi.cracking.aircrack_adapter import AircrackNgAdapter
from aegiswifi.cracking.dictionary import DictionaryManager
from aegiswifi.cracking.hashcat_adapter import HashcatAdapter
from aegiswifi.cracking.planner import CrackingPlanner
from aegiswifi.cracking.rules import RulesManager
from aegiswifi.cracking.schemas import (
    AttackMode,
    AttackStage,
    CrackingPlan,
    CrackingProgress,
    CrackingResult,
    DictionaryInfo,
    HashInfo,
    RuleInfo,
)
from aegiswifi.cracking.service import CrackingService, get_cracking_service

__all__ = [
    "AttackMode",
    "AttackStage",
    "CrackingPlan",
    "CrackingProgress",
    "CrackingResult",
    "DictionaryInfo",
    "HashInfo",
    "RuleInfo",
    "HashcatAdapter",
    "AircrackNgAdapter",
    "DictionaryManager",
    "RulesManager",
    "CrackingPlanner",
    "CrackingService",
    "get_cracking_service",
]
