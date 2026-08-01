"""REST API del módulo PMKID."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from aegiswifi.pmkid import service as pmkid_service
from aegiswifi.pmkid.schemas import PMKIDCaptureRequest, PMKIDCaptureStatusRead

router = APIRouter(prefix="/pmkid", tags=["pmkid"])


@router.post("/capture", response_model=PMKIDCaptureStatusRead, status_code=status.HTTP_201_CREATED)
async def start_pmkid_capture(req: PMKIDCaptureRequest) -> PMKIDCaptureStatusRead:
    return await pmkid_service.start_pmkid_capture(
        interface=req.interface,
        bssid=req.bssid,
        channel=req.channel,
        duration=req.duration,
    )


@router.get("/captures", response_model=list[PMKIDCaptureStatusRead])
def list_pmkid_captures() -> list[PMKIDCaptureStatusRead]:
    return pmkid_service.list_pmkid_captures()


@router.get("/captures/{capture_id}", response_model=PMKIDCaptureStatusRead)
def get_pmkid_capture(capture_id: str) -> PMKIDCaptureStatusRead:
    capture = pmkid_service.get_pmkid_capture(capture_id)
    if not capture:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Captura PMKID '{capture_id}' no encontrada",
        )
    return capture


@router.post("/captures/{capture_id}/stop", response_model=PMKIDCaptureStatusRead)
async def stop_pmkid_capture(capture_id: str) -> PMKIDCaptureStatusRead:
    capture = await pmkid_service.stop_pmkid_capture(capture_id)
    if not capture:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Captura PMKID '{capture_id}' no encontrada",
        )
    return capture
