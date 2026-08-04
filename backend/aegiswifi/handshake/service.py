"""Servicio de captura de handshake EAPOL (minuta §15, §17).

Orquesta la captura dirigida de handshakes WPA/WPA2 mediante
``airodump-ng`` filtrado por BSSID/canal, con deauth asistida opcional
vía ``aireplay-ng``.
"""

from __future__ import annotations

import asyncio
import hashlib
import shutil
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session
from structlog import get_logger

from aegiswifi.core.privileged import (
    run_aireplay_privileged,
    run_privileged_cmd,
    spawn_privileged_process,
)
from aegiswifi.handshake.schemas import CaptureStatus, HandshakeCaptureStatusRead
from aegiswifi.scope.service import build_policy_engine

log = get_logger(__name__)

# Capturas activas en memoria.
_captures: dict[str, dict[str, Any]] = {}


async def start_capture(
    engagement_id: int,
    interface: str,
    bssid: str,
    channel: int | None = None,
    duration: int = 120,
    deauth_assisted: bool = False,
    deauth_count: int = 3,
    db_session: Session | None = None,
) -> HandshakeCaptureStatusRead:
    """Inicia una captura dirigida de handshake EAPOL.

    1. Lanza ``airodump-ng`` filtrado por ``--bssid`` y ``--channel``.
    2. Si ``deauth_assisted``, ejecuta deauth limitada tras 5 s.
    3. Monitorea el archivo .cap para detectar EAPOL frames.
    4. Al detectar o expirar, detiene y valida con ``hcxpcapngtool``.
    """
    if db_session is None:
        raise ValueError("se requiere una sesión para validar el alcance")
    engine = build_policy_engine(db_session, engagement_id)
    engine.assert_allowed("handshake_capture", bssid=bssid, channel=channel)
    if deauth_assisted:
        engine.assert_allowed("controlled_reconnect", bssid=bssid, channel=channel)
        engine.assert_within_frame_budget()

    capture_id = str(uuid.uuid4())[:8]
    output_dir = Path(tempfile.mkdtemp(prefix="hs_capture_"))
    output_prefix = str(output_dir / "capture")

    # Comando airodump-ng filtrado por BSSID
    args = [
        "airodump-ng",
        "--bssid",
        bssid,
        "--write",
        output_prefix,
        "--write-interval",
        "1",
    ]
    if channel:
        args.extend(["--channel", str(channel)])
    args.append(interface)

    proc = await spawn_privileged_process(args)
    if proc is None:
        entry: dict[str, Any] = {
            "id": capture_id,
            "engagement_id": engagement_id,
            "status": CaptureStatus.FAILED,
            "interface": interface,
            "bssid": bssid,
            "channel": channel,
            "started_at": datetime.now(UTC),
            "elapsed_seconds": 0,
            "handshake_detected": False,
            "error": "No se pudo iniciar airodump-ng",
        }
        _captures[capture_id] = entry
        return HandshakeCaptureStatusRead(**entry)

    entry = {
        "id": capture_id,
        "engagement_id": engagement_id,
        "status": CaptureStatus.CAPTURING,
        "interface": interface,
        "bssid": bssid,
        "channel": channel,
        "started_at": datetime.now(UTC),
        "elapsed_seconds": 0,
        "handshake_detected": False,
        "pcap_path": None,
        "hash_path": None,
        "error": None,
        "_process": proc,
        "_deauth_proc": None,
        "_output_dir": output_dir,
        "_output_prefix": output_prefix,
        "_duration": duration,
        "_deauth_assisted": deauth_assisted,
        "_deauth_count": deauth_count,
    }
    _captures[capture_id] = entry

    # Lanzar tarea de monitoreo en background
    asyncio.create_task(_monitor_capture(capture_id))

    return HandshakeCaptureStatusRead(**_public_fields(entry))


async def _monitor_capture(capture_id: str) -> None:
    """Monitorea la captura hasta detectar handshake o timeout."""
    entry = _captures.get(capture_id)
    if not entry:
        return

    proc = entry["_process"]
    duration = entry["_duration"]
    deauth_assisted = entry["_deauth_assisted"]
    deauth_count = entry["_deauth_count"]
    bssid = entry["bssid"]
    interface = entry["interface"]

    try:
        # Esperar 5 s antes de deauth asistida
        if deauth_assisted:
            await asyncio.sleep(5)
            if entry["status"] == CaptureStatus.CAPTURING:
                deauth_args = [
                    "--deauth",
                    str(deauth_count),
                    "-a",
                    bssid,
                    "--ignore-negative-one",
                    interface,
                ]
                await run_aireplay_privileged(deauth_args, timeout=15)
                log.info(
                    "deauth assisted sent",
                    bssid=bssid,
                    count=deauth_count,
                )

        # Monitorear hasta duración máxima
        start = asyncio.get_event_loop().time()
        cap_path = Path(f"{entry['_output_prefix']}-01.cap")

        while (asyncio.get_event_loop().time() - start) < duration:
            if entry["status"] != CaptureStatus.CAPTURING:
                break

            entry["elapsed_seconds"] = int(asyncio.get_event_loop().time() - start)

            # Verificar si el proceso terminó
            if proc.returncode is not None:
                break

            # Verificar si el cap file tiene un handshake válido convertible
            if cap_path.exists() and cap_path.stat().st_size > 0:
                # En lugar de usar aircrack-ng (que da falsos positivos),
                # forzamos la conversión real a .22000. Si esto tiene éxito,
                # sabemos 100% que el handshake es válido y podemos detener la captura.
                hash_path, conv_error = await _convert_to_22000(str(cap_path))
                if hash_path:
                    entry["handshake_detected"] = True
                    entry["pcap_path"] = str(cap_path)
                    entry["hash_path"] = hash_path
                    log.info(
                        "handshake detected and converted successfully",
                        bssid=bssid,
                        capture_id=capture_id,
                    )
                    break

            await asyncio.sleep(2)

        # Detener airodump-ng
        if proc.returncode is None:
            proc.terminate()
            try:
                await asyncio.wait_for(proc.wait(), timeout=5)
            except TimeoutError:
                proc.kill()
                await proc.wait()

        # Guardar pcap_path si existe
        if cap_path.exists() and cap_path.stat().st_size > 0:
            entry["pcap_path"] = str(cap_path)

            if entry["handshake_detected"] and entry.get("hash_path"):
                entry["status"] = CaptureStatus.COMPLETE
            elif entry["status"] == CaptureStatus.CAPTURING:
                entry["status"] = CaptureStatus.FAILED
                entry["error"] = (
                    "Timeout: no se detectó handshake válido en el tiempo establecido (no se pudo convertir a .22000)."
                )

            # Persistir siempre el original antes de validar (minuta §15/§17/§30).
            try:
                from aegiswifi.core.config import get_settings
                from aegiswifi.database.engine import get_sessionmaker
                from aegiswifi.database.models import AccessPoint
                from aegiswifi.database.models import Capture as DBCapture
                from aegiswifi.validation.service import get_validation_service

                with get_sessionmaker()() as db_session:
                    ap = db_session.scalar(
                        select(AccessPoint).where(
                            AccessPoint.engagement_id == entry["engagement_id"],
                            AccessPoint.bssid == entry["bssid"],
                        )
                    )
                    evidence_dir = (
                        get_settings().paths.evidence_dir
                        / str(entry["engagement_id"])
                        / "captures"
                    )
                    evidence_dir.mkdir(parents=True, exist_ok=True)
                    evidence_path = evidence_dir / f"handshake_{capture_id}_{uuid.uuid4().hex[:8]}.cap"
                    sha256 = hashlib.sha256()
                    size_bytes = 0
                    with cap_path.open("rb") as source, evidence_path.open("xb") as destination:
                        while chunk := source.read(1024 * 1024):
                            sha256.update(chunk)
                            size_bytes += len(chunk)
                            destination.write(chunk)

                    db_cap = DBCapture(
                        engagement_id=entry["engagement_id"],
                        path=str(evidence_path),
                        category="handshake",
                        format="cap",
                        sha256=sha256.hexdigest(),
                        original_filename=cap_path.name,
                        size_bytes=size_bytes,
                        interface=entry["interface"],
                        channel=entry["channel"],
                        bssid=entry["bssid"],
                        ssid=ap.ssid if ap else None,
                        tool="airodump-ng",
                    )
                    db_session.add(db_cap)
                    db_session.commit()
                    db_session.refresh(db_cap)

                    val_service = get_validation_service()
                    result = await val_service.validate_capture(
                        capture=db_cap, db_session=db_session, force=True
                    )
                    entry["pcap_path"] = str(evidence_path)
                    entry["handshake_detected"] = result.validated
                    if result.artifact_id:
                        entry["artifact_id"] = result.artifact_id
                    if result.validated:
                        entry["status"] = CaptureStatus.COMPLETE
                        entry["hash_path"] = result.hash22000_path
                    else:
                        entry["status"] = CaptureStatus.FAILED
                        entry["error"] = "; ".join(result.errors) or "La captura no contiene un handshake utilizable"
            except Exception as e:
                log.error("Error al persistir/validar captura en DB", error=str(e))
        elif entry["status"] == CaptureStatus.CAPTURING:
            entry["status"] = CaptureStatus.FAILED
            entry["error"] = "No se generó ningún archivo de captura."

    except Exception as exc:
        log.error("capture monitoring error", capture_id=capture_id, error=str(exc))
        entry["status"] = CaptureStatus.FAILED
        entry["error"] = str(exc)
    finally:
        # Garantizar que airodump-ng se detenga SIEMPRE (incluso en caso de error/cancelación)
        if proc and proc.returncode is None:
            try:
                proc.terminate()
                await asyncio.wait_for(proc.wait(), timeout=3)
            except Exception:
                try:
                    proc.kill()
                    await proc.wait()
                except Exception:
                    pass
        output_dir = entry.get("_output_dir")
        if output_dir:
            shutil.rmtree(output_dir, ignore_errors=True)


async def _check_handshake(cap_path: str, bssid: str) -> bool:
    """Verifica si un archivo .cap contiene un handshake EAPOL completo."""
    stdout, stderr, rc = await run_privileged_cmd(
        ["aircrack-ng", cap_path],
        timeout=15,
    )
    combined = (stdout + stderr).lower()
    return "1 handshake" in combined or "wpa (1 handshake)" in combined or "handshake" in combined


async def _convert_to_22000(cap_path: str) -> tuple[str | None, str | None]:
    """Convierte un .cap con handshake a formato .22000 para Hashcat."""
    hash_path = cap_path.replace(".cap", ".22000")

    # 1. Intentar con hcxpcapngtool (estándar moderno)
    stdout, stderr, rc = await run_privileged_cmd(
        ["hcxpcapngtool", "-o", hash_path, cap_path],
        timeout=15,
    )
    if Path(hash_path).exists() and Path(hash_path).stat().st_size > 0:
        return hash_path, None

    error_hcx = stderr.strip() if stderr else stdout.strip()

    # 2. Fallback a aircrack-ng -j (Aircrack >= 1.7 genera .hc22000)
    # Aircrack-ng añade automáticamente la extensión, así que le pasamos el prefijo
    prefix_path = cap_path.replace(".cap", "")
    await run_privileged_cmd(
        ["aircrack-ng", cap_path, "-j", prefix_path],
        timeout=15,
    )

    # Aircrack-ng puede generar archivo.hc22000 o archivo.hccapx
    possible_outputs = [f"{prefix_path}.hc22000", f"{prefix_path}.hccapx", f"{prefix_path}.22000"]
    for p in possible_outputs:
        if Path(p).exists() and Path(p).stat().st_size > 0:
            # Renombrar al estándar interno (.22000)
            if p != hash_path:
                try:
                    Path(p).rename(hash_path)
                except Exception:
                    pass
            return hash_path, None

    return None, f"hcxpcapngtool: {error_hcx} | aircrack-ng fallback también falló."


async def stop_capture(capture_id: str) -> HandshakeCaptureStatusRead | None:
    """Detiene una captura activa."""
    entry = _captures.get(capture_id)
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

    entry["status"] = CaptureStatus.STOPPED
    return HandshakeCaptureStatusRead(**_public_fields(entry))


def get_capture(capture_id: str) -> HandshakeCaptureStatusRead | None:
    """Obtiene el estado de una captura."""
    entry = _captures.get(capture_id)
    if not entry:
        return None
    return HandshakeCaptureStatusRead(**_public_fields(entry))


def list_captures() -> list[HandshakeCaptureStatusRead]:
    """Lista todas las capturas."""
    return [HandshakeCaptureStatusRead(**_public_fields(e)) for e in _captures.values()]


def _public_fields(entry: dict[str, Any]) -> dict[str, Any]:
    """Filtra campos internos (prefijo _) del diccionario."""
    return {k: v for k, v in entry.items() if not k.startswith("_")}
