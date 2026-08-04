"""REST API + WebSocket del módulo de descubrimiento (minuta §14, §37).

Endpoints:
  GET    /api/v1/discovery/status       — estado del escaneo
  POST   /api/v1/discovery/scan/start   — iniciar escaneo
  POST   /api/v1/discovery/scan/stop    — detener escaneo
  GET    /api/v1/discovery/aps          — listar APs
  GET    /api/v1/discovery/aps/{bssid}  — detalle de AP
  GET    /api/v1/discovery/clients      — listar clientes
  GET    /api/v1/discovery/snapshot     — snapshot completo
  GET    /api/v1/discovery/degraded     — APs con seguridad degradada
  GET    /api/v1/discovery/events       — eventos recientes
  GET    /api/v1/discovery/export       — exportar inventario

WebSocket:
  GET    /api/v1/ws/discovery           — eventos en tiempo real
"""

from __future__ import annotations

import asyncio

import structlog
from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect, status

from aegiswifi.discovery import service as discovery_service
from aegiswifi.discovery.schemas import (
    AccessPointDetail,
    ClientSummary,
    InventoryExport,
    InventoryFilter,
    InventorySnapshot,
    ScanConfig,
    ScanStatus,
)

router = APIRouter(prefix="/discovery", tags=["discovery"])
ws_router = APIRouter(prefix="/ws", tags=["discovery_ws"])


# ── Estado ──────────────────────────────────────────────────────────


@router.get("/status", response_model=ScanStatus)
async def get_status() -> ScanStatus:
    """Estado actual del escáner de descubrimiento."""
    return await discovery_service.get_scan_status()


# ── Escaneo ─────────────────────────────────────────────────────────


@router.post("/scan/start", response_model=ScanStatus)
async def start_scan(config: ScanConfig) -> ScanStatus:
    """Inicia un escaneo de descubrimiento en la interfaz indicada."""
    try:
        return await discovery_service.start_scan(config)
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        ) from e


@router.post("/scan/stop", response_model=ScanStatus)
async def stop_scan() -> ScanStatus:
    """Detiene el escaneo activo."""
    return await discovery_service.stop_scan()


# ── APs ─────────────────────────────────────────────────────────────


@router.get("/aps", response_model=list[AccessPointDetail])
async def list_aps(
    ssid: str | None = Query(None),
    bssid: str | None = Query(None),
    band: str | None = Query(None),
    channel: int | None = Query(None),
    protocol: str | None = Query(None),
    in_scope: bool | None = Query(None),
    wps: bool | None = Query(None),
    signal_min: int | None = Query(None),
    signal_max: int | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> list[AccessPointDetail]:
    """Lista Access Points descubiertos con filtros opcionales."""
    filters = InventoryFilter(
        ssid=ssid,
        bssid=bssid,
        band=band,
        channel=channel,
        protocol=protocol,
        in_scope=in_scope,
        wps=wps,
        signal_min=signal_min,
        signal_max=signal_max,
        limit=limit,
        offset=offset,
    )
    return await discovery_service.list_aps(filters)


@router.get("/aps/{bssid}", response_model=AccessPointDetail)
async def get_ap(bssid: str) -> AccessPointDetail:
    """Obtiene detalle de un AP por BSSID."""
    ap = await discovery_service.get_ap(bssid)
    if ap is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"AP {bssid} no encontrado",
        )
    return ap


# ── Clientes ────────────────────────────────────────────────────────


@router.get("/clients", response_model=list[ClientSummary])
async def list_clients() -> list[ClientSummary]:
    """Lista clientes descubiertos."""
    return await discovery_service.list_clients()


# ── Snapshot ────────────────────────────────────────────────────────


@router.get("/snapshot", response_model=InventorySnapshot)
async def get_snapshot() -> InventorySnapshot:
    """Snapshot completo del inventario actual."""
    return await discovery_service.get_inventory_snapshot()


# ── Análisis ────────────────────────────────────────────────────────


@router.get("/degraded", response_model=list[AccessPointDetail])
async def get_degraded() -> list[AccessPointDetail]:
    """APs con seguridad degradada."""
    return await discovery_service.find_degraded_aps()


@router.get("/events")
async def get_events(limit: int = Query(50, ge=1, le=500)) -> list[dict[str, object]]:
    """Eventos recientes de descubrimiento."""
    return await discovery_service.recent_events(limit)


# ── Export ──────────────────────────────────────────────────────────


@router.get("/export", response_model=InventoryExport)
async def export_inventory(
    ssid: str | None = Query(None),
    bssid: str | None = Query(None),
    protocol: str | None = Query(None),
) -> InventoryExport:
    """Exporta el inventario completo."""
    filters = InventoryFilter(
        ssid=ssid,
        bssid=bssid,
        protocol=protocol,
        limit=0,  # sin límite en export
    )
    return await discovery_service.export_inventory(filters)


# ── WebSocket ───────────────────────────────────────────────────────


@ws_router.websocket("/discovery")
async def discovery_ws(websocket: WebSocket) -> None:
    """WebSocket de eventos en tiempo real de descubrimiento.

    Envía el snapshot inicial al conectar, luego emite eventos
    a medida que el inventario cambia.
    """
    await websocket.accept()

    try:
        # Snapshot inicial
        snapshot = await discovery_service.get_inventory_snapshot()
        await websocket.send_json({"type": "snapshot", "data": snapshot.model_dump()})

        # Loop de eventos en tiempo real
        last_event_count = 0
        while True:
            events = await discovery_service.recent_events(limit=100)
            if len(events) > last_event_count:
                new_events = events[last_event_count:]
                for event in new_events:
                    await websocket.send_json({"type": "event", "data": event})
                last_event_count = len(events)

            # Pequeño sleep para no saturar el loop
            await asyncio.sleep(1)

    except WebSocketDisconnect:
        pass
    except Exception:
        # Log pero no crashear
        logger = structlog.get_logger(__name__)
        logger.exception("websocket error")
