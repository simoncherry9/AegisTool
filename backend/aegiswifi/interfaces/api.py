"""REST API del módulo de interfaces (minuta §13, §37).

Endpoints:
  GET    /api/v1/interfaces          — listar interfaces detectadas
  GET    /api/v1/interfaces/{name}   — info detallada de una interfaz
  POST   /api/v1/interfaces/{name}/prepare  — preparar para auditoría
  POST   /api/v1/interfaces/{name}/restore  — restaurar estado original
  GET    /api/v1/interfaces/diagnose — diagnóstico del sistema

Todas las operaciones son seguras (no requieren DB) y graceful si las
herramientas de sistema no están instaladas.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from aegiswifi.interfaces import service as interfaces_service
from aegiswifi.interfaces.schemas import (
    InterfaceDiagnostic,
    InterfacePrepareResult,
    InterfaceRestoreResult,
    WirelessInterface,
)

router = APIRouter(prefix="/interfaces", tags=["interfaces"])


@router.get("", response_model=list[WirelessInterface])
async def list_interfaces() -> list[WirelessInterface]:
    """Lista todas las interfaces inalámbricas detectadas.

    Ejecuta ``iw dev`` y complementa con ``iw phy`` y ``ethtool``.
    Retorna lista vacía si no hay interfaces o las herramientas no
    están instaladas.
    """
    return await interfaces_service.list_all_interfaces()


@router.get("/diagnose", response_model=InterfaceDiagnostic)
async def diagnose(
    name: str | None = Query(None, description="Interfaz a diagnosticar (opcional)"),
) -> InterfaceDiagnostic:
    """Diagnóstico completo del sistema de interfaces inalámbricas.

    Args:
        name: Nombre de la interfaz a diagnosticar. Si se omite,
              diagnostica el sistema completo.

    Returns:
        :class:`InterfaceDiagnostic` con rfkill, procesos conflictivos y health check.
    """
    return await interfaces_service.diagnose_interface(name)


@router.get("/{name}", response_model=WirelessInterface)
async def get_interface(name: str) -> WirelessInterface:
    """Obtiene información detallada de una interfaz específica.

    Args:
        name: Nombre de la interfaz (ej. ``wlan0``).

    Returns:
        :class:`WirelessInterface` con todos los datos detectados.

    Raises:
        404: Si la interfaz no existe.
    """
    iface = await interfaces_service.get_interface(name)
    if iface is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"interfaz '{name}' no encontrada",
        )
    return iface


@router.post("/{name}/prepare", response_model=InterfacePrepareResult)
async def prepare_interface(name: str) -> InterfacePrepareResult:
    """Prepara una interfaz para auditoría inalámbrica.

    1. Captura y persiste el estado original.
    2. Activa monitor mode.
    3. Prueba la capacidad de inyección.

    Args:
        name: Nombre de la interfaz física.

    Returns:
        :class:`InterfacePrepareResult` con el resultado.

    Raises:
        404: Si la interfaz no existe.
        500: Si no se puede preparar.
    """
    try:
        return await interfaces_service.prepare_interface(name)
    except RuntimeError as e:
        if "no encontrada" in str(e):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e),
            ) from e
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        ) from e


@router.post("/{name}/restore", response_model=InterfaceRestoreResult)
async def restore_interface(name: str) -> InterfaceRestoreResult:
    """Restaura una interfaz a su estado original.

    Recupera el estado guardado por ``prepare`` y revierte los cambios.
    Si no hay estado guardado, la operación se considera exitosa (no-op).

    Args:
        name: Nombre de la interfaz.

    Returns:
        :class:`InterfaceRestoreResult` con el resultado.
    """
    return await interfaces_service.restore_interface(name)
