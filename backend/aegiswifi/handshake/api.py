"""REST API del módulo de captura de handshake EAPOL (minuta §15, §17).

Endpoints:
  POST /handshake/capture     — iniciar captura dirigida
  GET  /handshake/captures    — listar capturas
  GET  /handshake/captures/{id} — detalle de una captura
  POST /handshake/captures/{id}/stop — detener captura
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from aegiswifi.handshake import service as handshake_service
from aegiswifi.handshake.schemas import HandshakeCaptureRequest, HandshakeCaptureStatusRead

router = APIRouter(prefix="/handshake", tags=["handshake"])


@router.post("/capture", response_model=HandshakeCaptureStatusRead, status_code=status.HTTP_201_CREATED)
async def start_handshake_capture(
    req: HandshakeCaptureRequest,
) -> HandshakeCaptureStatusRead:
    """Inicia una captura dirigida de handshake EAPOL."""
    return await handshake_service.start_capture(
        interface=req.interface,
        bssid=req.bssid,
        channel=req.channel,
        duration=req.duration,
        deauth_assisted=req.deauth_assisted,
        deauth_count=req.deauth_count,
    )


@router.get("/captures", response_model=list[HandshakeCaptureStatusRead])
def list_handshake_captures() -> list[HandshakeCaptureStatusRead]:
    """Lista todas las capturas de handshake dirigidas."""
    return handshake_service.list_captures()


@router.get("/captures/{capture_id}", response_model=HandshakeCaptureStatusRead)
def get_handshake_capture(capture_id: str) -> HandshakeCaptureStatusRead:
    """Obtiene el estado actual de una captura."""
    capture = handshake_service.get_capture(capture_id)
    if not capture:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Captura '{capture_id}' no encontrada",
        )
    return capture


@router.post("/captures/{capture_id}/stop", response_model=HandshakeCaptureStatusRead)
async def stop_handshake_capture(capture_id: str) -> HandshakeCaptureStatusRead:
    """Detiene una captura activa."""
    capture = await handshake_service.stop_capture(capture_id)
    if not capture:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Captura '{capture_id}' no encontrada",
        )
    return capture
