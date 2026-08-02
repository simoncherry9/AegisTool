"""Gestión de monitor mode e inyección en interfaces Wi-Fi (minuta §13, §37).

Proporciona funciones para activar/desactivar monitor mode, crear/eliminar
interfaces virtuales, testear inyección y verificar capacidades del hardware.
"""

from __future__ import annotations

import asyncio
from typing import cast

from structlog import get_logger

from aegiswifi.interfaces.detection import _run_iw, get_phy_info

from aegiswifi.core.privileged import (
    run_aireplay_privileged,
    run_airmon_privileged,
    run_ip_privileged,
    run_iw_privileged,
)

log = get_logger(__name__)


async def _run_aireplay(args: list[str], timeout: int = 15) -> tuple[str, str]:  # noqa: ASYNC109
    """Ejecuta ``aireplay-ng`` con privilegios sudo/root."""
    return await run_aireplay_privileged(args, timeout=timeout)


async def _run_ip(args: list[str], timeout: int = 10) -> tuple[str, str]:  # noqa: ASYNC109
    """Ejecuta ``ip`` con privilegios sudo/root para modificaciones de interfaz."""
    return await run_ip_privileged(args, timeout=timeout)


async def _run_airmon(args: list[str], timeout: int = 15) -> tuple[str, str]:  # noqa: ASYNC109
    """Ejecuta ``airmon-ng`` con privilegios sudo/root."""
    return await run_airmon_privileged(args, timeout=timeout)


async def _run_iw_mutating(args: list[str], timeout: int = 15) -> tuple[str, str]:  # noqa: ASYNC109
    """Ejecuta ``iw`` con privilegios sudo/root para operaciones que modifican estado."""
    return await run_iw_privileged(args, timeout=timeout)


# ── Capability checks ──────────────────────────────────────────────


async def check_monitor_support(phy: str) -> bool:
    """Verifica que el PHY soporte monitor mode.

    Consulta la información del PHY vía ``iw phy <phy> info`` y busca
    ``monitor`` en los modos de interfaz soportados.

    Args:
        phy: Nombre del PHY (ej. ``phy0``).

    Returns:
        ``True`` si monitor mode está soportado.
    """
    phy_info = await get_phy_info(phy)
    return "monitor" in phy_info.get("supported_modes", [])


async def check_ap_mode_support(phy: str) -> bool:
    """Verifica que el PHY soporte modo AP.

    Args:
        phy: Nombre del PHY (ej. ``phy0``).

    Returns:
        ``True`` si AP mode está soportado.
    """
    phy_info = await get_phy_info(phy)
    return "AP" in phy_info.get("supported_modes", [])


async def list_channels_for_band(phy: str, band_name: str) -> list[int]:
    """Lista los canales disponibles para una banda específica.

    Args:
        phy: Nombre del PHY (ej. ``phy0``).
        band_name: Nombre de la banda (ej. ``2.4 GHz``, ``5 GHz``).

    Returns:
        Lista de números de canal. Vacía si la banda no está soportada.
    """
    phy_info = await get_phy_info(phy)
    # For now we return all channels — the PHY info parser lumps them together.
    # A future enhancement could parse per-band channels.
    return cast(list[int], phy_info.get("channels", []))


# ── Monitor mode ───────────────────────────────────────────────────




async def enable_monitor_mode(interface: str) -> str:
    """Activa monitor mode en la interfaz.

    Estrategia:
    0. Si la interfaz (o <iface>mon) ya está en modo monitor, la retorna de inmediato.
    1. Ejecuta ``airmon-ng check kill`` y ``airmon-ng start <iface>`` (con sudo).
    2. Si airmon-ng no está disponible, realiza cambio manual vía ``ip link down``,
       ``iw set type monitor`` e ``ip link up``.
    3. Si falla, crea interfaz virtual ``<iface>mon``.
    """
    from aegiswifi.interfaces.detection import _parse_iw_dev_output

    # 0. Verificar si ya se encuentra en modo monitor
    iw_dev_init, _ = await _run_iw(["dev"])
    parsed_ifaces = _parse_iw_dev_output(iw_dev_init)

    for entry in parsed_ifaces:
        if entry["iface"] == interface and entry.get("type") == "monitor":
            log.info("interface is already in monitor mode", interface=interface)
            return interface

    mon_candidate = f"{interface}mon"
    for entry in parsed_ifaces:
        if entry["iface"] == mon_candidate and entry.get("type") == "monitor":
            log.info("virtual/renamed monitor interface already active", interface=mon_candidate)
            return mon_candidate

    # 1. Estrategia principal con airmon-ng (estándar en Kali Linux)
    await _run_airmon(["check", "kill"])
    airout, airerr = await _run_airmon(["start", interface])
    combined_air = airout + airerr

    if "password is required" in combined_air.lower() or "a password is required" in combined_air.lower():
        raise RuntimeError(
            f"Se requieren privilegios sudo para preparar {interface}. "
            "Por favor ingresa la contraseña sudo de Kali en la sección 'Herramientas del Sistema'."
        )

    if "command not found" not in combined_air.lower() and airout:
        if "monitor mode" in airout.lower() or "enabled" in airout.lower():
            import re

            m = re.search(r"monitor mode (?:enabled|started) (?:on|for)\s+([a-zA-Z0-9_\-]+)", airout, re.IGNORECASE)
            if m:
                mon_iface = m.group(1).rstrip(")")
                log.info("airmon-ng monitor mode enabled", interface=mon_iface)
                return mon_iface

        # Verificar qué pasó después de airmon-ng
        iw_out, _ = await _run_iw(["dev"])
        post_ifaces = _parse_iw_dev_output(iw_out)

        for entry in post_ifaces:
            if entry["iface"] == mon_candidate and entry.get("type") == "monitor":
                log.info("airmon-ng created monitor interface", interface=mon_candidate)
                return mon_candidate
            if entry["iface"] == interface and entry.get("type") == "monitor":
                log.info("airmon-ng set interface to monitor mode", interface=interface)
                return interface

    # 2. Estrategia directa ip link down + iw set monitor + ip link up
    await _run_ip(["link", "set", interface, "down"])
    stdout, stderr = await _run_iw_mutating(["dev", interface, "set", "type", "monitor"])
    if stderr and ("command failed" in stderr.lower() or "not permitted" in stderr.lower()):
        stdout, stderr = await _run_iw_mutating(["dev", interface, "set", "monitor", "control"])

    await _run_ip(["link", "set", interface, "up"])

    # Verificar que iw realmente funcionó (no asumir éxito si el binario no existe)
    if stderr and ("command not found" in stderr.lower() or "not found" in stderr.lower()):
        log.warning("iw binary not available for fallback", stderr=stderr.strip())
    elif not stderr or "command failed" not in stderr.lower():
        # Confirmar el cambio vía iw dev
        iw_check, _ = await _run_iw(["dev"])
        check_ifaces = _parse_iw_dev_output(iw_check)
        for entry in check_ifaces:
            if entry["iface"] == interface and entry.get("type") == "monitor":
                log.info("monitor mode enabled via iw", interface=interface)
                return interface
        # iw no confirmó monitor mode, seguir al siguiente fallback
        log.warning("iw set type monitor did not result in monitor mode", interface=interface)

    # 3. Estrategia interfaz virtual
    mon_name = f"{interface}mon"
    stdout, stderr = await _run_iw_mutating(["dev", interface, "interface", "add", mon_name, "type", "monitor"])
    if stderr and "command failed" in stderr.lower():
        raise RuntimeError(f"no se pudo activar monitor mode en {interface}: {stderr.strip()}")
    await _run_ip(["link", "set", mon_name, "up"])
    log.info("virtual monitor interface created", physical=interface, monitor=mon_name)
    return mon_name


async def disable_monitor_mode(interface: str) -> None:
    """Desactiva monitor mode volviendo a modo managed."""
    await _run_airmon(["stop", interface])
    await _run_ip(["link", "set", interface, "down"])
    stdout, stderr = await _run_iw_mutating(["dev", interface, "set", "type", "managed"])
    if stderr and "command failed" in stderr.lower():
        raise RuntimeError(f"no se pudo desactivar monitor mode en {interface}: {stderr.strip()}")
    await _run_ip(["link", "set", interface, "up"])
    log.info("monitor mode disabled", interface=interface)


async def create_virtual_monitor(physical: str, name: str | None = None) -> str:
    """Crea una interfaz monitor virtual sobre un PHY físico.

    Args:
        physical: Nombre de la interfaz física (ej. ``wlan0``).
        name: Nombre para la interfaz virtual. Si es ``None``, se usa
              ``<physical>mon``.

    Returns:
        Nombre de la interfaz virtual creada.

    Raises:
        RuntimeError: Si no se puede crear la interfaz virtual.
    """
    mon_name = name or f"{physical}mon"
    stdout, stderr = await _run_iw_mutating(
        [
            "dev",
            physical,
            "interface",
            "add",
            mon_name,
            "type",
            "monitor",
        ]
    )
    if stderr and "command failed" in stderr.lower():
        raise RuntimeError(
            f"no se pudo crear interfaz monitor virtual {mon_name} "
            f"sobre {physical}: {stderr.strip()}"
        )
    log.info("virtual monitor interface created", physical=physical, monitor=mon_name)
    return mon_name


async def remove_virtual_interface(name: str) -> None:
    """Elimina una interfaz virtual.

    Args:
        name: Nombre de la interfaz a eliminar.

    Raises:
        RuntimeError: Si no se puede eliminar.
    """
    stdout, stderr = await _run_iw_mutating(["dev", name, "del"])
    if stderr and "command failed" in stderr.lower():
        raise RuntimeError(f"no se pudo eliminar interfaz virtual {name}: {stderr.strip()}")
    log.info("virtual interface removed", interface=name)


# ── Injection test ─────────────────────────────────────────────────


async def test_injection(interface: str, timeout: int = 10) -> bool | None:  # noqa: ASYNC109
    """Prueba la capacidad de inyección de una interfaz.

    Ejecuta ``aireplay-ng -9 <interface>`` y analiza la salida.

    Args:
        interface: Nombre de la interfaz (debe estar en monitor mode).
        timeout: Tiempo máximo de espera en segundos.

    Returns:
        - ``True`` si la inyección funciona.
        - ``False`` si la inyección falla.
        - ``None`` si no se puede determinar (aireplay-ng no instalado).
    """
    stdout, stderr = await _run_aireplay(["-9", interface], timeout=timeout)

    # aireplay-ng no está instalado
    if not stdout and "command not found" in stderr:
        return None

    # Parse injection test result
    if "Injection is working" in stdout or "Injection is working" in stderr:
        return True
    if "No Answer" in stdout or "No Answer" in stderr:
        return False

    # Try to determine from exit status or lack of positive indicators
    combined = (stdout + "\n" + stderr).lower()
    if "couldn't" in combined or "failed" in combined or "error" in combined:
        return False

    # No clear signal — return None (inconclusive)
    log.info("injection test inconclusive", interface=interface)
    return None


# ── Interface state helpers ────────────────────────────────────────


async def get_interface_type(interface: str) -> str | None:
    """Obtiene el tipo actual de una interfaz vía ``iw dev``.

    Returns:
        Tipo de interfaz (``managed``, ``monitor``, ``AP``, etc.)
        o ``None`` si no se puede determinar.
    """
    stdout, stderr = await _run_iw(["dev"])
    if not stdout:
        return None

    # Find the interface and its type in the iw dev output
    found = False
    for line in stdout.splitlines():
        stripped = line.strip()
        if stripped.startswith("Interface " + interface):
            found = True
        if found and stripped.startswith("type "):
            return stripped[len("type ") :]

    return None
