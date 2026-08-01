"""Servicio de evaluación y ataques WPS."""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
import re
from typing import Any

from structlog import get_logger

from aegiswifi.core.privileged import (
    run_wash_privileged,
    spawn_privileged_process,
)
from aegiswifi.wps.schemas import (
    WpsAttackRequest,
    WpsAttackStatusEnum,
    WpsAttackStatusRead,
    WpsMethod,
    WpsScanResult,
)

log = get_logger(__name__)

_wps_attacks: dict[str, dict[str, Any]] = {}


async def scan_wps(interface: str) -> list[WpsScanResult]:
    """Escanea APs con WPS activado usando wash."""
    stdout, stderr = await run_wash_privileged(["-i", interface, "-s"], timeout=20)
    results: list[WpsScanResult] = []

    lines = (stdout + "\n" + stderr).splitlines()
    for line in lines:
        parts = line.split()
        if len(parts) >= 5 and re.match(r"^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$", parts[0]):
            bssid = parts[0]
            try:
                channel = int(parts[1])
            except ValueError:
                channel = None
            wps_locked = parts[4].lower() in ("yes", "1", "true")
            ssid = parts[-1] if len(parts) > 5 else None

            results.append(
                WpsScanResult(
                    bssid=bssid,
                    ssid=ssid,
                    channel=channel,
                    wps_locked=wps_locked,
                )
            )

    return results


async def start_wps_attack(req: WpsAttackRequest) -> WpsAttackStatusRead:
    attack_id = str(uuid.uuid4())[:8]

    if req.method == WpsMethod.BULLY:
        args = ["bully", "-b", req.bssid]
        if req.channel:
            args.extend(["-c", str(req.channel)])
        args.append(req.interface)
    elif req.method == WpsMethod.PIXIE_DUST:
        args = ["reaver", "-i", req.interface, "-b", req.bssid, "-K", "1", "-vv"]
        if req.channel:
            args.extend(["-c", str(req.channel)])
    else:  # BRUTE_FORCE
        args = ["reaver", "-i", req.interface, "-b", req.bssid, "-vv"]
        if req.channel:
            args.extend(["-c", str(req.channel)])

    proc = await spawn_privileged_process(args)
    if proc is None:
        entry: dict[str, Any] = {
            "id": attack_id,
            "status": WpsAttackStatusEnum.FAILED,
            "interface": req.interface,
            "bssid": req.bssid,
            "method": req.method,
            "started_at": datetime.now(timezone.utc),
            "elapsed_seconds": 0,
            "error": "No se pudo iniciar la herramienta WPS",
        }
        _wps_attacks[attack_id] = entry
        return WpsAttackStatusRead(**entry)

    entry = {
        "id": attack_id,
        "status": WpsAttackStatusEnum.RUNNING,
        "interface": req.interface,
        "bssid": req.bssid,
        "method": req.method,
        "started_at": datetime.now(timezone.utc),
        "elapsed_seconds": 0,
        "pin_found": None,
        "psk_found": None,
        "progress_pct": 0.0,
        "error": None,
        "_process": proc,
        "_timeout": req.timeout,
    }
    _wps_attacks[attack_id] = entry
    asyncio.create_task(_monitor_wps_attack(attack_id))
    return WpsAttackStatusRead(**_public_fields(entry))


async def _monitor_wps_attack(attack_id: str) -> None:
    entry = _wps_attacks.get(attack_id)
    if not entry:
        return
    proc = entry["_process"]
    timeout = entry["_timeout"]
    start = asyncio.get_event_loop().time()

    try:
        while (asyncio.get_event_loop().time() - start) < timeout:
            if entry["status"] != WpsAttackStatusEnum.RUNNING:
                break
            entry["elapsed_seconds"] = int(asyncio.get_event_loop().time() - start)
            if proc.returncode is not None:
                break
            await asyncio.sleep(2)

        if proc.returncode is None:
            proc.terminate()
            try:
                await asyncio.wait_for(proc.wait(), timeout=5)
            except TimeoutError:
                proc.kill()
                await proc.wait()

        if entry["status"] == WpsAttackStatusEnum.RUNNING:
            entry["status"] = WpsAttackStatusEnum.FAILED
            entry["error"] = "Ataque WPS finalizado sin PIN recuperado"
    except Exception as exc:
        log.error("wps attack error", error=str(exc))
        entry["status"] = WpsAttackStatusEnum.FAILED
        entry["error"] = str(exc)


async def stop_wps_attack(attack_id: str) -> WpsAttackStatusRead | None:
    entry = _wps_attacks.get(attack_id)
    if not entry:
        return None
    proc = entry.get("_process")
    if proc and proc.returncode is None:
        proc.terminate()
        try:
            await asyncio.wait_for(proc.wait(), timeout=5)
        except TimeoutError:
            proc.kill()
            await proc.wait()

    entry["status"] = WpsAttackStatusEnum.STOPPED
    return WpsAttackStatusRead(**_public_fields(entry))


def get_wps_attack(attack_id: str) -> WpsAttackStatusRead | None:
    entry = _wps_attacks.get(attack_id)
    return WpsAttackStatusRead(**_public_fields(entry)) if entry else None


def list_wps_attacks() -> list[WpsAttackStatusRead]:
    return [WpsAttackStatusRead(**_public_fields(e)) for e in _wps_attacks.values()]


def _public_fields(entry: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in entry.items() if not k.startswith("_")}
