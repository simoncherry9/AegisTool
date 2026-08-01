"""Servicio de captura PMKID vía hcxdumptool (minuta §16, §17)."""

from __future__ import annotations

import asyncio
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from structlog import get_logger

from aegiswifi.core.privileged import run_privileged_cmd, spawn_privileged_process
from aegiswifi.pmkid.schemas import PMKIDCaptureStatus, PMKIDCaptureStatusRead

log = get_logger(__name__)

_pmkid_captures: dict[str, dict[str, Any]] = {}


async def start_pmkid_capture(
    interface: str,
    bssid: str | None = None,
    channel: int | None = None,
    duration: int = 60,
) -> PMKIDCaptureStatusRead:
    capture_id = str(uuid.uuid4())[:8]
    output_dir = Path(tempfile.mkdtemp(prefix="pmkid_capture_"))
    output_pcap = str(output_dir / "capture.pcapng")

    args = ["hcxdumptool", "-i", interface, "-o", output_pcap, "--enable_status=1"]
    if channel:
        args.extend(["-c", str(channel)])

    proc = await spawn_privileged_process(args)
    if proc is None:
        entry: dict[str, Any] = {
            "id": capture_id,
            "status": PMKIDCaptureStatus.FAILED,
            "interface": interface,
            "bssid": bssid,
            "started_at": datetime.now(timezone.utc),
            "elapsed_seconds": 0,
            "pmkid_count": 0,
            "error": "No se pudo iniciar hcxdumptool",
        }
        _pmkid_captures[capture_id] = entry
        return PMKIDCaptureStatusRead(**entry)

    entry = {
        "id": capture_id,
        "status": PMKIDCaptureStatus.CAPTURING,
        "interface": interface,
        "bssid": bssid,
        "started_at": datetime.now(timezone.utc),
        "elapsed_seconds": 0,
        "pmkid_count": 0,
        "pcap_path": output_pcap,
        "hash_path": None,
        "error": None,
        "_process": proc,
        "_output_dir": output_dir,
        "_duration": duration,
    }
    _pmkid_captures[capture_id] = entry

    asyncio.create_task(_monitor_pmkid(capture_id))
    return PMKIDCaptureStatusRead(**_public_fields(entry))


async def _monitor_pmkid(capture_id: str) -> None:
    entry = _pmkid_captures.get(capture_id)
    if not entry:
        return

    proc = entry["_process"]
    duration = entry["_duration"]
    output_pcap = entry["pcap_path"]
    start = asyncio.get_event_loop().time()

    try:
        while (asyncio.get_event_loop().time() - start) < duration:
            if entry["status"] != PMKIDCaptureStatus.CAPTURING:
                break
            entry["elapsed_seconds"] = int(asyncio.get_event_loop().time() - start)

            if Path(output_pcap).exists() and Path(output_pcap).stat().st_size > 0:
                # Check for PMKID using hcxpcapngtool
                hash_path = output_pcap.replace(".pcapng", ".22000")
                stdout, stderr, rc = await run_privileged_cmd(
                    ["hcxpcapngtool", "-o", hash_path, output_pcap],
                    timeout=10,
                )
                if Path(hash_path).exists() and Path(hash_path).stat().st_size > 0:
                    entry["pmkid_count"] = 1
                    entry["hash_path"] = hash_path

            await asyncio.sleep(3)

        if proc.returncode is None:
            proc.terminate()
            try:
                await asyncio.wait_for(proc.wait(), timeout=5)
            except TimeoutError:
                proc.kill()
                await proc.wait()

        entry["status"] = PMKIDCaptureStatus.COMPLETE
    except Exception as exc:
        log.error("pmkid capture error", error=str(exc))
        entry["status"] = PMKIDCaptureStatus.FAILED
        entry["error"] = str(exc)


async def stop_pmkid_capture(capture_id: str) -> PMKIDCaptureStatusRead | None:
    entry = _pmkid_captures.get(capture_id)
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

    entry["status"] = PMKIDCaptureStatus.STOPPED
    return PMKIDCaptureStatusRead(**_public_fields(entry))


def get_pmkid_capture(capture_id: str) -> PMKIDCaptureStatusRead | None:
    entry = _pmkid_captures.get(capture_id)
    return PMKIDCaptureStatusRead(**_public_fields(entry)) if entry else None


def list_pmkid_captures() -> list[PMKIDCaptureStatusRead]:
    return [PMKIDCaptureStatusRead(**_public_fields(e)) for e in _pmkid_captures.values()]


def _public_fields(entry: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in entry.items() if not k.startswith("_")}
