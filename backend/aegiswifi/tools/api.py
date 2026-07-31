"""API REST para verificación de herramientas del sistema."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from aegiswifi.tools.schemas import ToolsCheckResult
from aegiswifi.tools.service import check_tools

router = APIRouter(prefix="/tools", tags=["tools"])


@router.get("/check", response_model=ToolsCheckResult)
async def tools_check() -> ToolsCheckResult:
    """Verifica qué herramientas del sistema están instaladas."""
    return check_tools()
