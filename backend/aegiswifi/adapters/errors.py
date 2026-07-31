"""Excepciones del sistema de adaptadores de herramientas externas (minuta §27)."""

from __future__ import annotations


class AdapterError(Exception):
    """Error base del sistema de adaptadores."""


class ToolNotInstalled(AdapterError):
    """La herramienta no está instalada en el sistema."""


class ToolExecutionError(AdapterError):
    """Error durante la ejecución de la herramienta."""


class OutputParseError(AdapterError):
    """Error al parsear la salida de la herramienta."""
