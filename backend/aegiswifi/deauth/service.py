"""Servicio de deauthentication controlada."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
import re

from structlog import get_logger

from aegiswifi.core.privileged import run_aireplay_privileged
from aegiswifi.deauth.schemas import DeauthResult

log = get_logger(__name__)

_deauth_history: list[DeauthResult] = []


async def send_deauth(
    interface: str,
    bssid: str,
    client_mac: str | None = None,
    count: int = 5,
    reason: str | None = None,
) -> DeauthResult:
    entry_id = str(uuid.uuid4())[:8]
    args = ["--deauth", str(count), "-a", bssid, "--ignore-negative-one"]
    if client_mac:
        args.extend(["-c", client_mac])
    args.append(interface)

    stdout, stderr = await run_aireplay_privileged(args, timeout=20)
    combined = stdout + stderr

    packets = count
    m = re.search(r"DeAuth (\d+)", combined)
    if m:
        packets = int(m.group(1))

    success = "command not found" not in combined and "failed" not in stderr.lower()

    result = DeauthResult(
        id=entry_id,
        success=success,
        packets_sent=packets if success else 0,
        interface=interface,
        bssid=bssid,
        client_mac=client_mac,
        timestamp=datetime.now(timezone.utc),
        error=stderr.strip() if not success else None,
    )
    _deauth_history.append(result)
    return result


def get_deauth_history() -> list[DeauthResult]:
    return list(_deauth_history)
