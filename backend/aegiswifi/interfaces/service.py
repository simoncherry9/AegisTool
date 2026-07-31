"""Orquestación del ciclo de vida de interfaces Wi-Fi (Fase 3, minuta §37).

La capa de servicio coordina detección, monitor mode, test de inyección,
restauración y diagnóstico, exponiendo una API limpia para las capas
superiores (REST, CLI, Jobs).
"""

from __future__ import annotations

from structlog import get_logger

from aegiswifi.interfaces.detection import (
    check_rfkill,
    detect_conflicting_processes,
    get_interface_details,
    list_interfaces,
)
from aegiswifi.interfaces.monitor import (
    create_virtual_monitor,
    enable_monitor_mode,
    test_injection,
)
from aegiswifi.interfaces.restoration import (
    capture_current_state,
    save_interface_state,
)
from aegiswifi.interfaces.restoration import (
    restore_interface as _restore_interface,
)
from aegiswifi.interfaces.schemas import (
    InterfaceDiagnostic,
    InterfacePrepareResult,
    InterfaceRestoreResult,
    WirelessInterface,
)

log = get_logger(__name__)


async def get_interface(name: str) -> WirelessInterface | None:
    """Obtiene información detallada de una interfaz por nombre.

    Args:
        name: Nombre de la interfaz (ej. ``wlan0``).

    Returns:
        :class:`WirelessInterface` o ``None`` si no se encuentra.
    """
    return await get_interface_details(name)


async def list_all_interfaces() -> list[WirelessInterface]:
    """Lista todas las interfaces inalámbricas detectadas.

    Returns:
        Lista de :class:`WirelessInterface`. Vacía si no hay interfaces
        o las herramientas no están instaladas.
    """
    return await list_interfaces()


async def prepare_interface(name: str, *, create_virtual: bool = False) -> InterfacePrepareResult:
    """Prepara una interfaz para auditoría inalámbrica.

    Flujo completo:
    1. Captura el estado actual de la interfaz.
    2. Persiste el estado original (para restauración futura).
    3. Activa monitor mode (directo o virtual).
    4. Prueba la capacidad de inyección.
    5. Retorna el resultado completo.

    Args:
        name: Nombre de la interfaz física (ej. ``wlan0``).
        create_virtual: Si es ``True``, crea una interfaz virtual monitor
            en lugar de cambiar el tipo de la física.

    Returns:
        :class:`InterfacePrepareResult` con el resultado de la operación.

    Raises:
        RuntimeError: Si la interfaz no existe o no se puede preparar.
    """
    # 1. Verify interface exists
    iface = await get_interface_details(name)
    if iface is None:
        raise RuntimeError(f"interfaz {name} no encontrada")

    # 2. Capture current state
    state = await capture_current_state(name)

    # 3. Save state
    save_interface_state(state)

    # 4. Enable monitor mode
    monitor_iface = name
    if create_virtual:
        monitor_iface = await create_virtual_monitor(name)
        log.info("created virtual monitor", physical=name, virtual=monitor_iface)
    else:
        monitor_iface = await enable_monitor_mode(name)
        log.info("monitor mode enabled", interface=monitor_iface)

    # 5. Test injection
    injection_ok = await test_injection(monitor_iface)
    log.info(
        "injection test result",
        interface=monitor_iface,
        result=injection_ok,
    )

    return InterfacePrepareResult(
        interface=name,
        monitor_interface=monitor_iface,
        mode_set=True,
        injection_ok=injection_ok,
        original_state=state,
    )


async def restore_interface(name: str) -> InterfaceRestoreResult:
    """Restaura una interfaz a su estado original.

    Args:
        name: Nombre de la interfaz.

    Returns:
        :class:`InterfaceRestoreResult` con el resultado.
    """
    # Get current type for the result
    current_type = "unknown"
    iface = await get_interface_details(name)
    if iface:
        current_type = iface.type

    # Perform restoration (silently handles no-state case)
    restored = await _restore_interface(name)

    # Refresh current type after restoration
    iface_after = await get_interface_details(name)
    final_type = iface_after.type if iface_after else current_type

    return InterfaceRestoreResult(
        interface=name,
        restored=restored,
        current_type=final_type,
    )


async def diagnose_interface(name: str | None = None) -> InterfaceDiagnostic:
    """Realiza un diagnóstico completo del sistema de interfaces.

    Args:
        name: Nombre de la interfaz a diagnosticar. Si es ``None``,
              diagnostica el sistema completo.

    Returns:
        :class:`InterfaceDiagnostic` con hallazgos.
    """
    issues: list[str] = []

    # Check rfkill
    rfkill_blocks = await check_rfkill()
    rfkill_active = any(b.get("soft") is True or b.get("hard") is True for b in rfkill_blocks)

    if rfkill_active:
        blocked_types = [
            str(b.get("type", "unknown")) for b in rfkill_blocks if b.get("soft") or b.get("hard")
        ]
        issues.append(f"rfkill bloquea: {', '.join(blocked_types)}")

    # Check conflicting processes
    processes = await detect_conflicting_processes()
    if processes:
        issues.append(f"procesos conflictivos detectados: {', '.join(processes[:5])}")

    # Check specific interface or general presence
    present = False
    if name:
        iface = await get_interface_details(name)
        if iface is not None:
            present = True
            if iface.blocked:
                issues.append(f"interfaz {name} bloqueada")
        else:
            issues.append(f"interfaz {name} no encontrada")
    else:
        # General system check
        all_ifaces = await list_interfaces()
        present = len(all_ifaces) > 0
        if not present:
            issues.append("no se detectaron interfaces inalámbricas")

    return InterfaceDiagnostic(
        interface=name,
        present=present,
        blocked=rfkill_active,
        conflicting_processes=processes,
        rfkill_blocks=rfkill_blocks,
        issues=issues,
    )
