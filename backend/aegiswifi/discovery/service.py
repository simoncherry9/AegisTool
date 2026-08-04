"""Orquestación del módulo de descubrimiento (minuta §14, §37).

Coordina el ciclo de vida del escaneo, las consultas al inventario
y el análisis de seguridad. Expone una API limpia que consumen
tanto el módulo REST como el CLI.

Usa singletons de módulo (``_inventory``, ``_scanner``) porque solo
una sesión de descubrimiento puede estar activa a la vez.
"""

from __future__ import annotations

from typing import Any

from structlog import get_logger

from aegiswifi.discovery.inventory import DiscoveryInventory
from aegiswifi.discovery.scanner import AirodumpScanner, _scan_available
from aegiswifi.discovery.schemas import (
    AccessPointDetail,
    ClientSummary,
    InventoryExport,
    InventoryFilter,
    InventorySnapshot,
    ScanConfig,
    ScanStatus,
)

log = get_logger(__name__)

# ── Singletons de módulo ────────────────────────────────────────────

_inventory = DiscoveryInventory()
_scanner: AirodumpScanner | None = None


def _get_scanner() -> AirodumpScanner | None:
    global _scanner
    return _scanner


def _set_scanner(s: AirodumpScanner | None) -> None:
    global _scanner
    _scanner = s


# ── Callback ────────────────────────────────────────────────────────


def _on_scan_update(aps_data: list[dict[str, Any]], clients_data: list[dict[str, Any]]) -> None:
    """Callback invocado por el scanner en cada actualización CSV."""
    import asyncio

    loop = asyncio.get_event_loop()
    if loop.is_closed():
        return

    async def _update() -> None:
        for ap in aps_data:
            try:
                await _inventory.upsert_ap(ap)
            except Exception as exc:
                log.warning("upsert_ap failed", bssid=ap.get("bssid"), error=str(exc))
        for client in clients_data:
            try:
                await _inventory.upsert_client(client)
            except Exception as exc:
                log.warning("upsert_client failed", mac=client.get("station_mac"), error=str(exc))

    asyncio.run_coroutine_threadsafe(_update(), loop)


# ── Operaciones de escaneo ──────────────────────────────────────────


async def reset_inventory() -> None:
    """Limpia el inventario actual."""
    await _inventory.clear()
    log.info("inventory reset")


async def start_scan(config: ScanConfig) -> ScanStatus:
    """Inicia un escaneo en la interfaz especificada.

    Args:
        config: Configuración del escaneo.

    Returns:
        Estado del escaneo tras el arranque.
    """
    scanner = _get_scanner()
    if scanner is not None and scanner.running:
        log.warning("scan already running", interface=scanner.interface)
        return await get_scan_status()

    # Verificar disponibilidad de airodump-ng
    available = await _scan_available()
    if not available:
        log.warning("airodump-ng not available, using mock mode")
        # Continuamos igual — las funciones devuelven vacío gracefulmente

    # Limpiar inventario anterior
    await reset_inventory()

    scanner = AirodumpScanner(
        interface=config.interface,
        on_update=_on_scan_update,
    )

    success = await scanner.start(channel=config.channel)
    if not success:
        return ScanStatus(error="failed to start airodump-ng")

    _set_scanner(scanner)
    log.info("scan started", interface=config.interface, channel=config.channel)

    return ScanStatus(
        running=True,
        interface=config.interface,
        channel=config.channel,
        started_at=None,
    )


async def stop_scan() -> ScanStatus:
    """Detiene el escaneo activo."""
    scanner = _get_scanner()
    if scanner is None or not scanner.running:
        return ScanStatus()

    try:
        await scanner.stop()
    except Exception as exc:
        log.error("error stopping scan", error=str(exc))

    _set_scanner(None)
    log.info("scan stopped")

    return ScanStatus()


async def get_scan_status() -> ScanStatus:
    """Retorna el estado actual del escaneo."""
    scanner = _get_scanner()
    if scanner is None or not scanner.running:
        return ScanStatus()

    return ScanStatus(
        running=True,
        interface=scanner.interface,
        channel=scanner._channel,
        uptime_seconds=scanner.uptime_seconds,
        ap_count=_inventory.ap_count,
        client_count=_inventory.client_count,
    )


async def set_scan_channel(channel: int) -> ScanStatus:
    """Cambia el canal del escaneo activo."""
    scanner = _get_scanner()
    if scanner is None or not scanner.running:
        return ScanStatus()

    try:
        await scanner.set_channel(channel)
    except Exception as exc:
        log.error("error setting channel", channel=channel, error=str(exc))
        return ScanStatus(error=str(exc))

    return await get_scan_status()


# ── Consultas de inventario ─────────────────────────────────────────


async def list_aps(filters: InventoryFilter | None = None) -> list[AccessPointDetail]:
    """Lista APs en el inventario."""
    return await _inventory.list_aps(filters)


async def list_clients(filters: InventoryFilter | None = None) -> list[ClientSummary]:
    """Lista clientes en el inventario."""
    return await _inventory.list_clients(filters)


async def get_ap(bssid: str) -> AccessPointDetail | None:
    """Obtiene un AP por BSSID."""
    return await _inventory.get_ap(bssid)


async def get_inventory_snapshot() -> InventorySnapshot:
    """Toma un snapshot completo del inventario."""
    status = await get_scan_status()
    return await _inventory.snapshot(status)


async def export_inventory(
    filters: InventoryFilter | None = None,
) -> InventoryExport:
    """Exporta el inventario."""
    return await _inventory.export(filters)


async def find_degraded_aps() -> list[AccessPointDetail]:
    """Encuentra APs con seguridad degradada."""
    return await _inventory.find_degraded()


async def find_aps_with_wps() -> list[AccessPointDetail]:
    """Encuentra APs con WPS habilitado."""
    return await _inventory.find_aps_with_wps()


async def recent_events(limit: int = 50) -> list[dict[str, object]]:
    """Retorna los eventos más recientes."""
    events = await _inventory.recent_events(limit)
    return [e.model_dump() for e in events]
