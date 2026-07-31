"""Schemas para verificación de herramientas del sistema."""

from __future__ import annotations

from pydantic import BaseModel


class ToolInfo(BaseModel):
    """Información de una herramienta del sistema."""

    name: str
    binary: str
    installed: bool
    version: str | None = None
    description: str
    category: str  # cracking | capture | analysis | interface | utility


class ToolsCheckResult(BaseModel):
    """Resultado de la verificación de herramientas."""

    tools: list[ToolInfo]
    total: int
    installed: int
    missing: int
    os: str  # linux | windows | darwin
