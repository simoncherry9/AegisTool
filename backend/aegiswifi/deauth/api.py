"""REST API del módulo de deauthentication."""

from __future__ import annotations

from fastapi import APIRouter, status

from aegiswifi.deauth import service as deauth_service
from aegiswifi.deauth.schemas import DeauthRequest, DeauthResult

router = APIRouter(prefix="/deauth", tags=["deauth"])


@router.post("/send", response_model=DeauthResult, status_code=status.HTTP_200_OK)
async def send_deauth_packets(req: DeauthRequest) -> DeauthResult:
    return await deauth_service.send_deauth(
        interface=req.interface,
        bssid=req.bssid,
        client_mac=req.client_mac,
        count=req.count,
        reason=req.reason,
    )


@router.get("/history", response_model=list[DeauthResult])
def list_deauth_history() -> list[DeauthResult]:
    return deauth_service.get_deauth_history()
