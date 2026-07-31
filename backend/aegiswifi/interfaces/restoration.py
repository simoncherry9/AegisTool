"""Persistencia de estado de interfaces y restauración (minuta §13, §37).

Guarda el estado original de una interfaz antes de modificarla y permite
restaurarlo completamente. El estado se persiste como JSON en
``data/interface_states/`` para sobrevivir reinicios de la aplicación.
"""

from __future__ import annotations

from contextlib import suppress

from structlog import get_logger

from aegiswifi.core.config import REPO_ROOT
from aegiswifi.interfaces.detection import _run_iw
from aegiswifi.interfaces.monitor import (
    _run_ip,
    disable_monitor_mode,
    remove_virtual_interface,
)
from aegiswifi.interfaces.schemas import InterfaceState

log = get_logger(__name__)

# Directorio donde se persisten los estados de interfaces.
_STATE_DIR = REPO_ROOT / "data" / "interface_states"


# ── Persistencia ───────────────────────────────────────────────────


def save_interface_state(state: InterfaceState) -> None:
    """Persiste el estado de una interfaz a disco.

    El archivo se almacena en ``data/interface_states/{interface}.json``.

    Args:
        state: Estado de la interfaz a persistir.
    """
    _STATE_DIR.mkdir(parents=True, exist_ok=True)
    path = _STATE_DIR / f"{state.interface}.json"
    path.write_text(state.model_dump_json(indent=2), encoding="utf-8")
    log.info("interface state saved", interface=state.interface, path=str(path))


def load_interface_state(interface: str) -> InterfaceState | None:
    """Carga el estado guardado de una interfaz.

    Args:
        interface: Nombre de la interfaz.

    Returns:
        :class:`InterfaceState` o ``None`` si no hay estado guardado.
    """
    path = _STATE_DIR / f"{interface}.json"
    if not path.exists():
        return None
    try:
        return InterfaceState.model_validate_json(path.read_text(encoding="utf-8"))
    except Exception as exc:
        log.warning("cannot load interface state", interface=interface, error=str(exc))
        return None


def delete_interface_state(interface: str) -> None:
    """Elimina el archivo de estado de una interfaz.

    Se invoca tras una restauración exitosa para limpiar el estado persistido.
    No lanza error si el archivo no existe.

    Args:
        interface: Nombre de la interfaz.
    """
    path = _STATE_DIR / f"{interface}.json"
    path.unlink(missing_ok=True)
    log.info("interface state deleted", interface=interface)


# ── Captura de estado ──────────────────────────────────────────────


async def capture_current_state(interface: str) -> InterfaceState:
    """Captura el estado actual de una interfaz antes de modificarla.

    Lee el tipo de interfaz, estado up/down y canal actual.

    Args:
        interface: Nombre de la interfaz.

    Returns:
        :class:`InterfaceState` con la información capturada.
    """
    # Obtener tipo actual
    iface_type = "managed"
    channel: int | None = None

    stdout, stderr = await _run_iw(["dev"])
    found = False

    if stdout:
        for line in stdout.splitlines():
            stripped = line.strip()
            if stripped.startswith("Interface " + interface):
                found = True
                continue
            if found and stripped.startswith("type "):
                iface_type = stripped[len("type ") :]
                continue
            if found and stripped.startswith("channel "):
                chan_str = stripped[len("channel ") :].split(",")[0].split()[0]
                with suppress(ValueError):
                    channel = int(chan_str)

    # Obtener estado up/down
    was_up = await _is_interface_up(interface)

    return InterfaceState(
        interface=interface,
        original_type=iface_type,
        original_channel=channel,
        was_up=was_up,
    )


async def _is_interface_up(interface: str) -> bool:
    """Verifica si una interfaz está arriba (state UP) vía ``ip link``."""
    stdout, stderr = await _run_ip(["link", "show", interface])
    if not stdout:
        return False
    return "state UP" in stdout or "state UNKNOWN" in stdout


# ── Restauración ───────────────────────────────────────────────────


async def restore_interface(interface: str) -> bool:
    """Restaura una interfaz a su estado original guardado.

    Pasos:
    1. Carga el estado guardado desde ``data/interface_states/{interface}.json``.
    2. Si existe una interfaz virtual monitor asociada, la elimina.
    3. Restaura el tipo original (managed).
    4. Sube/baja la interfaz según el estado original.
    5. Elimina el archivo de estado.

    Args:
        interface: Nombre de la interfaz.

    Returns:
        ``True`` si la restauración fue exitosa.
    """
    state = load_interface_state(interface)

    if state is None:
        log.info("no saved state to restore", interface=interface)
        return True  # Nothing to restore is considered success

    try:
        # 1. Remove virtual monitor interface if it exists
        mon_name = f"{interface}mon"
        with suppress(RuntimeError):
            await remove_virtual_interface(mon_name)

        # 2. Restore original type
        if state.original_type == "managed":
            with suppress(RuntimeError):
                await disable_monitor_mode(interface)
        elif state.original_type == "monitor":
            # Leave as monitor if that was the original state
            pass

        # 3. Restore up/down state
        is_up = await _is_interface_up(interface)
        if state.was_up and not is_up:
            await _run_ip(["link", "set", interface, "up"])
        elif not state.was_up and is_up:
            await _run_ip(["link", "set", interface, "down"])

        # 4. Clean up state file
        delete_interface_state(interface)

        log.info("interface restored", interface=interface)
        return True

    except Exception as exc:
        log.error("interface restoration failed", interface=interface, error=str(exc))
        return False
