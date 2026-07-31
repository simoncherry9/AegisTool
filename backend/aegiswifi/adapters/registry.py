"""Registro de adaptadores de herramientas (minuta §27).

Mapea ``job.kind`` → clase del adaptador concreto.
"""

from __future__ import annotations

from typing import Any

from aegiswifi.adapters.base import ToolAdapter

_ADAPTERS: dict[str, type[ToolAdapter]] = {}


def register_adapter(kind: str, adapter_cls: type[ToolAdapter]) -> None:
    """Registra un adaptador para un tipo de trabajo."""
    _ADAPTERS[kind] = adapter_cls


def get_adapter(kind: str, **kwargs: Any) -> ToolAdapter:
    """Retorna una instancia del adaptador registrado para ``kind``.

    Lanza :class:`ValueError` si no hay adaptador registrado.
    """
    cls = _ADAPTERS.get(kind)
    if cls is None:
        raise ValueError(f"no adapter registered for job kind: {kind}")
    return cls(**kwargs)


def list_adapters() -> dict[str, str]:
    """Retorna el mapeo ``kind → tool_name`` de todos los adaptadores registrados."""
    return {k: v.tool_name for k, v in _ADAPTERS.items()}
