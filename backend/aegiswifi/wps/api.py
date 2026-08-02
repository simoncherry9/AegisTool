"""REST API del módulo WPS."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from aegiswifi.wps import service as wps_service
from aegiswifi.wps.schemas import (
    WpsAttackRequest,
    WpsAttackStatusRead,
    WpsScanRequest,
    WpsScanResult,
)

router = APIRouter(prefix="/wps", tags=["wps"])


@router.post("/scan", response_model=list[WpsScanResult])
async def scan_wps_aps(req: WpsScanRequest) -> list[WpsScanResult]:
    return await wps_service.scan_wps(req.interface)


@router.post("/attack", response_model=WpsAttackStatusRead, status_code=status.HTTP_201_CREATED)
async def start_wps_attack(req: WpsAttackRequest) -> WpsAttackStatusRead:
    return await wps_service.start_wps_attack(req)


@router.get("/attacks", response_model=list[WpsAttackStatusRead])
def list_wps_attacks() -> list[WpsAttackStatusRead]:
    return wps_service.list_wps_attacks()


@router.get("/attacks/{attack_id}", response_model=WpsAttackStatusRead)
def get_wps_attack(attack_id: str) -> WpsAttackStatusRead:
    attack = wps_service.get_wps_attack(attack_id)
    if not attack:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ataque WPS '{attack_id}' no encontrado",
        )
    return attack


@router.post("/attacks/{attack_id}/stop", response_model=WpsAttackStatusRead)
async def stop_wps_attack(attack_id: str) -> WpsAttackStatusRead:
    attack = await wps_service.stop_wps_attack(attack_id)
    if not attack:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ataque WPS '{attack_id}' no encontrado",
        )
    return attack
