"""Gestión de monitor mode e inyección en interfaces Wi-Fi (minuta §13, §37).

Proporciona funciones para activar/desactivar monitor mode, crear/eliminar
interfaces virtuales, testear inyección y verificar capacidades del hardware.
"""

from __future__ import annotations

import asyncio
from typing import cast

from structlog import get_logger

from aegiswifi.interfaces.detection import _run_iw, get_phy_info

log = get_logger(__name__)


async def _run_aireplay(args: list[str], timeout: int = 15) -> tuple[str, str]:  # noqa: ASYNC109
    """Ejecuta ``aireplay-ng``. Retorna ``("", err)`` si falla."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "aireplay-ng",
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except TimeoutError:
            proc.kill()
            await proc.wait()
            return "", "timeout"
        return stdout.decode(errors="replace"), stderr.decode(errors="replace")
    except FileNotFoundError:
        return "", "aireplay-ng: command not found"
    except OSError as exc:
        log.warning("aireplay-ng execution error", error=str(exc))
        return "", str(exc)


async def _run_ip(args: list[str], timeout: int = 10) -> tuple[str, str]:  # noqa: ASYNC109
    """Ejecuta ``ip``. Retorna ``("", err)`` si falla."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "ip",
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except TimeoutError:
            proc.kill()
            await proc.wait()
            return "", "timeout"
        return stdout.decode(errors="replace"), stderr.decode(errors="replace")
    except FileNotFoundError:
        return "", "ip: command not found"
    except OSError as exc:
        log.warning("ip execution error", error=str(exc))
        return "", str(exc)


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
    1. Intenta ``iw dev <iface> set monitor control`` (cambio directo).
    2. Si falla, crea una interfaz virtual ``<iface>mon`` de tipo monitor.

    Args:
        interface: Nombre de la interfaz (ej. ``wlan0``).

    Returns:
        Nombre de la interfaz que está en monitor mode (puede ser la misma
        o una virtual recién creada).

    Raises:
        RuntimeError: Si no se puede activar monitor mode.
    """
    # First attempt: direct switch
    stdout, stderr = await _run_iw(["dev", interface, "set", "monitor", "control"])
    if not stderr or "command failed" not in stderr.lower():
        log.info("monitor mode enabled", interface=interface)
        return interface

    # Second attempt: create virtual monitor
    mon_name = f"{interface}mon"
    stdout, stderr = await _run_iw(
        [
            "dev",
            interface,
            "interface",
            "add",
            mon_name,
            "type",
            "monitor",
        ]
    )
    if stderr and "command failed" in stderr.lower():
        raise RuntimeError(f"no se pudo activar monitor mode en {interface}: {stderr.strip()}")
    log.info("virtual monitor interface created", physical=interface, monitor=mon_name)
    return mon_name


async def disable_monitor_mode(interface: str) -> None:
    """Desactiva monitor mode volviendo a modo managed.

    Args:
        interface: Nombre de la interfaz (puede ser física o virtual).

    Raises:
        RuntimeError: Si no se puede restaurar a modo managed.
    """
    stdout, stderr = await _run_iw(["dev", interface, "set", "type", "managed"])
    if stderr and "command failed" in stderr.lower():
        raise RuntimeError(f"no se pudo desactivar monitor mode en {interface}: {stderr.strip()}")
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
    stdout, stderr = await _run_iw(
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
    stdout, stderr = await _run_iw(["dev", name, "del"])
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
