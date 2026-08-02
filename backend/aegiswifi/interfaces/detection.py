"""Detección de interfaces inalámbricas, chipset y driver (minuta §13).

Todas las funciones que invocan herramientas externas lo hacen a través de
funciones ``_run_*()`` que son facilmene mockeables en tests con
:func:`unittest.mock.patch`.

Flujo típico::

    interfaces = await list_interfaces()
    for iface in interfaces:
        details = await get_interface_details(iface.name)
"""

from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import Any

from structlog import get_logger

from aegiswifi.interfaces.schemas import WirelessInterface

log = get_logger(__name__)

# ── Reusable patterns ──────────────────────────────────────────────

_RE_IW_DEV_BLOCK = re.compile(
    r"phy#(?P<phy>\d+)\s*\n"
    r"(?:\s+Interface\s+(?P<iface>\S+)\s*\n"
    r"(?:\s+ifindex\s+\d+\s*\n)?"
    r"(?:\s+wdev\s+\S+\s*\n)?"
    r"(?:\s+addr\s+(?P<addr>\S+)\s*\n)?"
    r"(?:\s+ssid\s+.*\n)?"
    r"(?:\s+type\s+(?P<type>\S+)\s*\n)?"
    r"(?:\s+channel\s+\S+\s*\n)?"
    r"(?:\s+txpower\s+\S+\s*\n)?"
    r")?",
    re.MULTILINE,
)

_RE_PHY_BAND = re.compile(
    r"Band\s+(?P<band>\d+(?:\.\d+)?\s*GHz):\s*\n"
    r"(?:(?!\tBand\s|\tSupported interface modes)[\s\S]*?)?"
    r"\t\* [\s\S]*?(?=\n\tBand|\n\tSupported interface modes|\Z)",
)

_RE_PHY_FREQ = re.compile(r"\t\* (?P<freq>\d+)\s+MHz\s+\[(?P<chan>\d+)\]")

_RE_PHY_MODE = re.compile(r"\t\* (?P<mode>\S+(?:\s+\S+)*)")

_RE_ETHTOOL_DRIVER = re.compile(r"driver:\s+(?P<driver>\S+)", re.MULTILINE)
_RE_ETHTOOL_VERSION = re.compile(r"version:\s+(?P<version>\S+)", re.MULTILINE)


from aegiswifi.core.privileged import run_privileged_cmd

# ── Subprocess wrappers (mockeables) ───────────────────────────────


async def _run_iw(args: list[str], timeout: int = 15) -> tuple[str, str]:  # noqa: ASYNC109
    """Ejecuta ``iw`` con los argumentos dados.

    ``iw dev`` / ``iw phy`` son comandos de solo lectura que **no requieren
    sudo**.  Ejecutarlos con ``run_privileged_cmd`` fallaba silenciosamente
    cuando la contraseña sudo no estaba configurada, devolviendo cadena vacía
    y provocando "no hay interfaces disponibles".
    """
    try:
        proc = await asyncio.create_subprocess_exec(
            "iw", *args,
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
        return "", "iw: command not found"
    except OSError as exc:
        log.warning("iw execution error", error=str(exc))
        return "", str(exc)


async def _run_ethtool(args: list[str], timeout: int = 10) -> tuple[str, str]:  # noqa: ASYNC109
    """Ejecuta ``ethtool`` con los argumentos dados.

    ``ethtool -i`` es un comando de solo lectura que **no requiere sudo**.
    """
    try:
        proc = await asyncio.create_subprocess_exec(
            "ethtool", *args,
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
        return "", "ethtool: command not found"
    except OSError as exc:
        log.warning("ethtool execution error", error=str(exc))
        return "", str(exc)



async def _run_airmon(args: list[str], timeout: int = 15) -> tuple[str, str]:  # noqa: ASYNC109
    """Ejecuta ``airmon-ng``. Retorna ``("", err)`` si falla."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "airmon-ng",
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
        return "", "airmon-ng: command not found"
    except OSError as exc:
        log.warning("airmon-ng execution error", error=str(exc))
        return "", str(exc)


async def _run_rfkill(args: list[str], timeout: int = 10) -> tuple[str, str]:  # noqa: ASYNC109
    """Ejecuta ``rfkill``. Retorna ``("", err)`` si falla."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "rfkill",
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
        return "", "rfkill: command not found"
    except OSError as exc:
        log.warning("rfkill execution error", error=str(exc))
        return "", str(exc)


# ── Parsers ────────────────────────────────────────────────────────


def _parse_iw_dev_output(output: str) -> list[dict[str, str]]:
    """Parsea la salida de ``iw dev``.

    Returns:
        Una lista de diccionarios con claves ``phy``, ``iface``, ``addr``, ``type``.
        Cada entrada representa una interfaz detectada.
    """
    interfaces: list[dict[str, str]] = []
    current_phy: str | None = None

    for line in output.splitlines():
        stripped = line.strip()
        if stripped.startswith("phy#"):
            current_phy = stripped[4:]  # "phy#0" → "0"
            continue
        if stripped.startswith("Interface "):
            iface = stripped[len("Interface ") :]
            interfaces.append({"phy": current_phy or "", "iface": iface, "addr": "", "type": ""})
            continue
        if interfaces and stripped.startswith("addr "):
            interfaces[-1]["addr"] = stripped[len("addr ") :]
        if interfaces and stripped.startswith("type "):
            interfaces[-1]["type"] = stripped[len("type ") :]

    return interfaces


def _parse_iw_phy_info(output: str) -> dict[str, Any]:
    """Parsea la salida de ``iw phy <phy> info``.

    Returns:
        Diccionario con ``bands``, ``channels``, ``supported_modes``.
    """
    result: dict[str, Any] = {
        "bands": [],
        "channels": [],
        "supported_modes": [],
    }

    in_band = False
    current_band: str | None = None
    modes_started = False

    for line in output.splitlines():
        stripped = line.strip()

        # Detect band headers (iw output: "Band 1:", "Band 2:")
        band_match = re.match(r"Band\s+(\d+):", stripped)
        if band_match:
            band_num = int(band_match.group(1))
            # Map iw band numbers to human-readable names
            band_name = {1: "2.4 GHz", 2: "5 GHz", 3: "6 GHz"}.get(band_num, f"Band {band_num}")
            current_band = band_name
            result["bands"].append(band_name)
            in_band = True
            modes_started = False
            continue

        # Detect supported interface modes section
        if "Supported interface modes" in stripped:
            modes_started = True
            in_band = False
            continue

        # Extract channel numbers within a band
        if in_band and current_band:
            chan_match = re.match(r"\s*\* (\d+) MHz \[(\d+)\]", stripped)
            if chan_match:
                chan = int(chan_match.group(2))
                if chan not in result["channels"]:
                    result["channels"].append(chan)

        # Extract supported modes
        if modes_started and stripped.startswith("* "):
            mode = stripped[2:].strip()
            if mode and mode not in result["supported_modes"]:
                result["supported_modes"].append(mode)

        # End of modes section
        if modes_started and stripped and not stripped.startswith("*"):
            modes_started = False

    result["channels"].sort()
    return result


def _parse_ethtool_output(output: str) -> dict[str, str]:
    """Parsea la salida de ``ethtool -i <interface>``.

    Returns:
        Diccionario con ``driver``, ``version``, ``firmware-version`` (opcional).
    """
    result: dict[str, str] = {}
    for line in output.splitlines():
        if ": " in line:
            key, value = line.split(": ", 1)
            result[key.strip()] = value.strip()
    return result


def _parse_rfkill_output(output: str) -> list[dict[str, object]]:
    """Parsea la salida de ``rfkill list``.

    Returns:
        Lista de diccionarios con ``id``, ``type``, ``soft``, ``hard``.
    """
    blocks: list[dict[str, object]] = []
    current: dict[str, object] = {}
    for line in output.splitlines():
        stripped = line.strip()
        if not stripped:
            if current:
                blocks.append(current)
                current = {}
            continue
        if re.match(r"^\d+:", stripped):
            if current:
                blocks.append(current)
            idx = stripped.split(":", 1)[0].strip()
            desc = stripped.split(":", 1)[1].strip() if ":" in stripped else ""
            current = {"id": int(idx), "type": desc, "soft": False, "hard": False}
        elif "Soft blocked: yes" in stripped:
            current["soft"] = True
        elif "Hard blocked: yes" in stripped:
            current["hard"] = True
    if current:
        blocks.append(current)
    return blocks


# ── Core detection functions ───────────────────────────────────────


async def list_interfaces() -> list[WirelessInterface]:
    """Lista todas las interfaces inalámbricas detectadas vía ``iw dev``.

    Para cada interfaz, completa chipset, driver, PHY, MAC y bandas/canales
    consultando ``iw phy``, ``ethtool`` y ``/sys``.

    Returns:
        Lista de :class:`WirelessInterface`. Vacía si no hay interfaces
        o ``iw`` no está instalado.
    """
    stdout, stderr = await _run_iw(["dev"])
    if not stdout and stderr:
        log.info("no iw output (tool may be missing)", stderr=stderr.strip())
        return []

    raw = _parse_iw_dev_output(stdout)
    if not raw:
        return []

    interfaces: list[WirelessInterface] = []
    for entry in raw:
        phy = entry.get("phy", "")
        iface_name = entry.get("iface", "")
        if not iface_name:
            continue

        # Get PHY details for bands/channels/modes
        phy_info: dict[str, Any] = {}
        if phy:
            phy_info = await get_phy_info(f"phy{phy}")

        # Detect driver
        driver, driver_ver = await detect_driver(iface_name)

        # Detect chipset
        chipset = None
        if phy:
            chipset = await detect_chipset(f"phy{phy}")

        iface = WirelessInterface(
            name=iface_name,
            phy=f"phy{phy}" if phy else None,
            mac=entry.get("addr") or None,
            chipset=chipset,
            driver=driver or None,
            driver_version=driver_ver or None,
            bands=phy_info.get("bands", []),
            channels=phy_info.get("channels", []),
            supported_modes=phy_info.get("supported_modes", []),
            type=entry.get("type", "managed"),
            monitor_mode=entry.get("type") == "monitor",
            ap_mode=entry.get("type") == "AP",
        )
        interfaces.append(iface)

    return interfaces


async def get_interface_details(name: str) -> WirelessInterface | None:
    """Obtiene información detallada de una interfaz por nombre.

    Consulta ``iw dev``, filtra por nombre, y completa con PHY, driver y chipset.

    Returns:
        :class:`WirelessInterface` o ``None`` si no se encuentra.
    """
    all_ifaces = await list_interfaces()
    for iface in all_ifaces:
        if iface.name == name:
            return iface
    return None


async def get_phy_info(phy: str) -> dict[str, Any]:
    """Ejecuta ``iw phy <phy> info`` y parsea bandas, canales y modos.

    Returns:
        Diccionario con ``bands``, ``channels``, ``supported_modes``.
    """
    if not phy:
        return {"bands": [], "channels": [], "supported_modes": []}
    stdout, stderr = await _run_iw(["phy", phy, "info"])
    if not stdout:
        log.info("no iw phy info output", phy=phy, stderr=stderr.strip())
        return {"bands": [], "channels": [], "supported_modes": []}
    return _parse_iw_phy_info(stdout)


async def detect_chipset(phy: str) -> str | None:
    """Detecta el chipset de un PHY vía sysfs.

    Lee ``/sys/class/ieee80211/<phy>/device/...`` para obtener información
    del fabricante y dispositivo.

    Args:
        phy: Nombre del PHY (ej. ``phy0``).

    Returns:
        Nombre del chipset o ``None`` si no se puede detectar.
    """
    device_path = Path(f"/sys/class/ieee80211/{phy}/device")
    if not device_path.exists():  # noqa: ASYNC240
        return None

    try:
        # Try to read modalias for vendor/device info
        modalias_path = device_path / "modalias"
        if modalias_path.exists():  # noqa: ASYNC240
            modalias = await asyncio.to_thread(modalias_path.read_text, encoding="utf-8")
            modalias = modalias.strip()
            # Format: usb:vXXXXpYYYY... or pci:v...
            # We just report the raw modalias as it's the most reliable
            # information available without udev admin database
            if "v" in modalias and "p" in modalias:
                return modalias

        # Fallback: read uevent for driver info
        uevent_path = device_path / "uevent"
        if uevent_path.exists():  # noqa: ASYNC240
            uevent = await asyncio.to_thread(uevent_path.read_text, encoding="utf-8")
            for line in uevent.splitlines():
                if line.startswith("DRIVER="):
                    return line.split("=", 1)[1].strip()
    except OSError as exc:
        log.debug("cannot read chipset info", phy=phy, error=str(exc))

    return None


async def detect_driver(interface: str) -> tuple[str | None, str | None]:
    """Detecta el driver y versión de una interfaz.

    Ejecuta ``ethtool -i <interface>`` y parsea la salida.

    Args:
        interface: Nombre de la interfaz (ej. ``wlan0``).

    Returns:
        ``(driver, version)``. Ambos pueden ser ``None`` si falla.
    """
    stdout, stderr = await _run_ethtool(["-i", interface])
    if not stdout:
        # Fallback: read from sysfs
        try:
            driver_path = Path(f"/sys/class/net/{interface}/device/driver")
            if driver_path.is_symlink():  # noqa: ASYNC240
                driver = driver_path.resolve().name  # noqa: ASYNC240
                return driver, None
        except OSError:
            pass
        return None, None

    parsed = _parse_ethtool_output(stdout)
    return parsed.get("driver"), parsed.get("version")


async def detect_conflicting_processes() -> list[str]:
    """Detecta procesos conflictivos vía ``airmon-ng check``.

    Returns:
        Lista de nombres de procesos conflictivos. Vacía si no hay o
        ``airmon-ng`` no está instalado.
    """
    stdout, stderr = await _run_airmon(["check"])
    if not stdout:
        return []

    processes: list[str] = []
    started = False
    for line in stdout.splitlines():
        stripped = line.strip()
        if "processes" in stripped.lower() and "could cause" in stripped.lower():
            started = True
            continue
        if started and stripped and not stripped.startswith("PID"):
            # Lines after the header are process names or process info
            # Format: "  PID    Name\n  1234   NetworkManager"
            parts = stripped.split()
            if len(parts) >= 2:
                try:
                    int(parts[0])  # PID
                    processes.append(" ".join(parts[1:]))
                except ValueError:
                    pass
    return processes


async def check_rfkill() -> list[dict[str, object]]:
    """Ejecuta ``rfkill list`` y retorna bloqueos detectados.

    Returns:
        Lista de bloqueos, cada uno con ``id``, ``type``, ``soft``, ``hard``.
        Vacía si no hay bloqueos o ``rfkill`` no está instalado.
    """
    stdout, stderr = await _run_rfkill(["list"])
    if not stdout:
        return []
    return _parse_rfkill_output(stdout)
