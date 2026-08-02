"""Servicio de captura de handshake EAPOL (minuta §15, §17).

Orquesta la captura dirigida de handshakes WPA/WPA2 mediante
``airodump-ng`` filtrado por BSSID/canal, con deauth asistida opcional
vía ``aireplay-ng``.
"""

from __future__ import annotations

import asyncio
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from structlog import get_logger

from aegiswifi.core.config import REPO_ROOT
from aegiswifi.core.privileged import (
    run_aireplay_privileged,
    run_privileged_cmd,
    spawn_privileged_process,
)
from aegiswifi.handshake.schemas import CaptureStatus, HandshakeCaptureStatusRead

log = get_logger(__name__)

# Capturas activas en memoria.
_captures: dict[str, dict[str, Any]] = {}


async def start_capture(
    interface: str,
    bssid: str,
    channel: int | None = None,
    duration: int = 120,
    deauth_assisted: bool = False,
    deauth_count: int = 3,
) -> HandshakeCaptureStatusRead:
    """Inicia una captura dirigida de handshake EAPOL.

    1. Lanza ``airodump-ng`` filtrado por ``--bssid`` y ``--channel``.
    2. Si ``deauth_assisted``, ejecuta deauth limitada tras 5 s.
    3. Monitorea el archivo .cap para detectar EAPOL frames.
    4. Al detectar o expirar, detiene y valida con ``hcxpcapngtool``.
    """
    capture_id = str(uuid.uuid4())[:8]
    output_dir = Path(tempfile.mkdtemp(prefix="hs_capture_"))
    output_prefix = str(output_dir / "capture")

    # Comando airodump-ng filtrado por BSSID
    args = [
        "airodump-ng",
        "--bssid", bssid,
        "--write", output_prefix,
        "--write-interval", "1",
    ]
    if channel:
        args.extend(["--channel", str(channel)])
    args.append(interface)

    proc = await spawn_privileged_process(args)
    if proc is None:
        entry: dict[str, Any] = {
            "id": capture_id,
            "status": CaptureStatus.FAILED,
            "interface": interface,
            "bssid": bssid,
            "channel": channel,
            "started_at": datetime.now(timezone.utc),
            "elapsed_seconds": 0,
            "handshake_detected": False,
            "error": "No se pudo iniciar airodump-ng",
        }
        _captures[capture_id] = entry
        return HandshakeCaptureStatusRead(**entry)

    entry = {
        "id": capture_id,
        "status": CaptureStatus.CAPTURING,
        "interface": interface,
        "bssid": bssid,
        "channel": channel,
        "started_at": datetime.now(timezone.utc),
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
                    "--deauth", str(deauth_count),
                    "-a", bssid,
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
                    log.info("handshake detected and converted successfully", bssid=bssid, capture_id=capture_id)
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

        # Post-procesamiento
        if entry["handshake_detected"] and entry.get("hash_path"):
            entry["status"] = CaptureStatus.COMPLETE
            
            # Integrar con ValidationService para que aparezca en el apartado de handshakes
            try:
                from aegiswifi.database.engine import SessionLocal
                from aegiswifi.validation.service import get_validation_service
                from aegiswifi.database.models import Capture as DBCapture
                from aegiswifi.database.models import Engagement, AccessPoint, EngagementStatus
                with SessionLocal() as db_session:
                    # Encontrar engagement activo (requerido para DB)
                    active_eng = db_session.query(Engagement).filter_by(status=EngagementStatus.ACTIVE.value).first()
                    # Si no hay activo, intentar obtener cualquiera para pruebas, o crear uno mínimo si falla todo
                    eng_id = active_eng.id if active_eng else 1
                    
                    # Encontrar el AP asociado
                    ap = db_session.query(AccessPoint).filter_by(bssid=entry["bssid"]).first()
                    ap_id = ap.id if ap else None

                    # Crear registro de Capture en DB
                    db_cap = DBCapture(
                        engagement_id=eng_id,
                        access_point_id=ap_id,
                        path=str(cap_path), 
                        category="handshake",
                        format="cap"
                    )
                    db_session.add(db_cap)
                    db_session.commit()
                    db_session.refresh(db_cap)
                    
                    val_service = get_validation_service()
                    result = await val_service.validate_capture(capture=db_cap, db_session=db_session, force=True)
                    if result.artifact_id:
                        entry["artifact_id"] = result.artifact_id
            except Exception as e:
                log.error("Error al validar automáticamente el handshake", error=str(e))
        elif entry["status"] == CaptureStatus.CAPTURING:
            entry["status"] = CaptureStatus.FAILED
            entry["error"] = "Timeout: no se detectó handshake válido en el tiempo establecido (no se pudo convertir a .22000)."

        # Guardar pcap_path si existe
        if cap_path.exists():
            entry["pcap_path"] = str(cap_path)

    except Exception as exc:
        log.error("capture monitoring error", capture_id=capture_id, error=str(exc))
        entry["status"] = CaptureStatus.FAILED
        entry["error"] = str(exc)


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
