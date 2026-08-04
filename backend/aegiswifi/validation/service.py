"""Servicio de validación de handshakes (minuta §15, §16, §28).

Analiza capturas en busca de handshakes EAPOL y PMKID mediante
hcxpcapngtool, clasifica la calidad y persiste los resultados en
:class:`HandshakeArtifact <aegiswifi.database.models.HandshakeArtifact>`.
"""

from __future__ import annotations

import asyncio
import os
import re
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from aegiswifi.database.models import (
    AccessPoint,
    Capture,
    HandshakeArtifact,
    HandshakeQuality,
)
from aegiswifi.validation.schemas import (
    QualityClassification,
    ValidationResult,
)

# Regex para detectar líneas de output de hcxpcapngtool.
_RE_HANDSHAKE = re.compile(r"handshake", re.IGNORECASE)
_RE_PMKID = re.compile(r"pmkid", re.IGNORECASE)
_RE_WRITTEN = re.compile(r"written", re.IGNORECASE)
_RE_EAPOL_MSG = re.compile(r"(M[1-4])", re.IGNORECASE)
_HEX_32 = re.compile(r"^[0-9a-fA-F]{32}$")

# Bits 0..2 del MESSAGEPAIR oficial de hashcat. Los pares 3 y 4 se
# conservan como diagnóstico, pero no se consideran aptos para auditoría.
_EAPOL_PAIR_INFO: dict[int, tuple[str, tuple[str, ...], float]] = {
    0: ("M1M2", ("M1", "M2"), 0.75),
    1: ("M1M4", ("M1", "M4"), 0.55),
    2: ("M2M3", ("M2", "M3"), 0.85),
    3: ("M2M3_UNCHECKED", ("M2", "M3"), 0.35),
    4: ("M3M4_UNCHECKED", ("M3", "M4"), 0.35),
    5: ("M3M4", ("M3", "M4"), 0.55),
}


class HandshakeValidationService:
    """Validador de handshakes EAPOL/PMKID.

    El flujo típico es:

    1. Recibir una captura (capture_id o file_path).
    2. Ejecutar ``hcxpcapngtool`` para extraer los hashes a formato .22000.
    3. Analizar la salida y el archivo .22000 generado.
    4. Clasificar la calidad del handshake.
    5. Crear o actualizar un :class:`HandshakeArtifact` en la BD.
    6. Retornar un :class:`ValidationResult`.
    """

    # Puntajes base por tipo de evidencia.
    _SCORE_M1 = 0.10
    _SCORE_M2 = 0.25
    _SCORE_M3 = 0.20
    _SCORE_M4 = 0.15
    _SCORE_PMKID = 0.30

    def __init__(self, hcxpcapngtool_path: str = "hcxpcapngtool") -> None:
        self._tool_path = hcxpcapngtool_path

    # ------------------------------------------------------------------
    # Validación principal
    # ------------------------------------------------------------------

    async def validate_capture(
        self,
        capture: Capture | None = None,
        file_path: str | None = None,
        db_session: Any = None,
        force: bool = False,
    ) -> ValidationResult:
        """Valida una captura y retorna el resultado.

        Args:
            capture: Objeto Capture de la BD (opcional).
            file_path: Ruta directa al archivo (alternativa a capture).
            db_session: Sesión de BD para persistir el artifact.
            force: Si ``True``, reprocesa aunque ya exista artifact.

        Returns:
            :class:`ValidationResult` con el análisis completo.
        """
        # Resolver archivo fuente.
        source_path = self._resolve_source(capture, file_path)
        if not source_path or not Path(source_path).is_file():
            return ValidationResult(
                errors=[f"Archivo no encontrado: {source_path}"],
                quality=QualityClassification.INVALID,
                source_file=source_path,
            )

        result = ValidationResult(
            capture_id=capture.id if capture else None,
            source_file=str(source_path),
        )

        # Verificar si ya existe un artifact validado.
        if capture and not force:
            existing = self._find_existing_artifact(capture, db_session)
            if existing and existing.validated:
                return self._artifact_to_result(existing, capture)

        # Ejecutar hcxpcapngtool.
        output_fd, output_path = tempfile.mkstemp(suffix=".22000")
        os.close(output_fd)

        try:
            stdout, stderr = await self._run_hcxpcapngtool(str(source_path), output_path)

            result.tool_output = (stdout + stderr)[:2000]

            if not Path(output_path).is_file() or os.path.getsize(output_path) == 0:
                # Fallback a aircrack-ng -j si hcxpcapngtool falla
                from aegiswifi.core.privileged import run_privileged_cmd

                prefix_path = str(source_path).replace(".cap", "").replace(".pcap", "")
                await run_privileged_cmd(
                    ["aircrack-ng", str(source_path), "-j", prefix_path], timeout=15
                )

                # Check possible output files
                for p in [
                    f"{prefix_path}.hc22000",
                    f"{prefix_path}.hccapx",
                    f"{prefix_path}.22000",
                ]:
                    if Path(p).exists() and Path(p).stat().st_size > 0:
                        shutil.copy2(p, output_path)
                        result.warnings.append(
                            "hcxpcapngtool falló, pero se recuperó usando aircrack-ng -j"
                        )
                        break

                if not Path(output_path).is_file() or os.path.getsize(output_path) == 0:
                    result.errors.append(
                        "Ni hcxpcapngtool ni aircrack-ng lograron extraer el handshake (posiblemente incompleto o corrupto)."
                    )

                    # Guardar el artifact de todos modos para que el usuario sepa que falló la validación
                    if db_session and capture:
                        artifact = self._persist_artifact(db_session, capture, result, "")
                        result.artifact_id = artifact.id
                    return result

            # Analizar el archivo .22000 generado.
            self._analyze_hashfile(Path(output_path), result)

            # Clasificar calidad.
            self._classify_quality(result)

            # Persistir artifact en BD si tenemos sesión y capture.
            if db_session and capture:
                artifact = self._persist_artifact(db_session, capture, result, output_path)
                result.artifact_id = artifact.id
                result.hash22000_path = artifact.hash22000_path

            return result

        except FileNotFoundError:
            result.errors.append("hcxpcapngtool no está instalado en el sistema")
            return result
        except Exception as exc:
            result.errors.append(f"Error durante validación: {exc}")
            return result
        finally:
            # El archivo de conversión siempre es temporal. Si no se persistió,
            # no devolver una ruta que dejará de existir.
            if not result.artifact_id and result.hash22000_path == output_path:
                result.hash22000_path = None
            if Path(output_path).exists():
                os.unlink(output_path)

    # ------------------------------------------------------------------
    # Análisis del hash 22000
    # ------------------------------------------------------------------

    def _analyze_hashfile(self, hash_path: Path, result: ValidationResult) -> None:
        """Analiza el archivo .22000 generado por hcxpcapngtool.

        Formatos aceptados::

            WPA*01*PMKID*MAC_AP*MAC_CLIENT*ESSID***MESSAGEPAIR
            WPA*02*MIC*MAC_AP*MAC_CLIENT*ESSID*NONCE_AP*EAPOL_CLIENT*MESSAGEPAIR
        """
        result.hash22000_path = str(hash_path)
        content = hash_path.read_text(encoding="utf-8", errors="replace")
        lines = [l.strip() for l in content.split("\n") if l.strip()]
        if not lines:
            return

        first = lines[0]
        result.hash22000_line = first[:80]

        # Cada línea es un hash distinto.
        for line in lines:
            self._parse_22000_line(line, result)

    def _parse_22000_line(self, line: str, result: ValidationResult) -> None:
        """Parse una línea de formato 22000.

        Distingue PMKID (``WPA*01``) de EAPOL (``WPA*02``) y lee el
        ``MESSAGEPAIR`` desde el noveno campo, no desde el MIC/PMKID.
        """
        if not line.startswith("WPA"):
            return

        fields = line.split("*")
        if len(fields) < 6 or fields[0] != "WPA":
            return

        hash_type = fields[1]
        if hash_type == "01":
            pmkid = fields[2]
            if not _HEX_32.fullmatch(pmkid):
                return
            result.kind = "pmkid"
            result.pmkid.detected = True
            result.pmkid.raw_value = pmkid
            result.pmkid.hash_line = line[:80]
            if result.message_pair is None:
                result.message_pair = fields[8] if len(fields) > 8 and fields[8] else "PMKID"
            return

        if hash_type != "02" or len(fields) < 9 or not _HEX_32.fullmatch(fields[2]):
            return

        try:
            pair_value = int(fields[8], 16)
        except ValueError:
            return
        pair_info = _EAPOL_PAIR_INFO.get(pair_value & 0x07)
        if pair_info is None:
            return

        pair_name, messages, pair_score = pair_info
        result.kind = "eapol"
        for message in messages:
            if message not in result.eapol.messages_found:
                result.eapol.messages_found.append(message)
        if pair_name not in result.eapol.pairs_complete:
            result.eapol.pairs_complete.append(pair_name)
        result.eapol.has_m12 = result.eapol.has_m12 or pair_name == "M1M2"
        result.eapol.has_m14 = result.eapol.has_m14 or pair_name == "M1M4"

        current_score = self._score_message_pair(result.message_pair)
        if result.message_pair is None or pair_score > current_score:
            result.message_pair = fields[8].upper().zfill(2)

    def _is_full_handshake(self, msg_pair: str) -> bool:
        """Determina si el par de mensajes representa un handshake completo.

        El campo MESSAGEPAIR de hashcat es un bitmask, no una enumeración de
        mensajes. Esta función se conserva para entradas descriptivas antiguas.
        """
        return "M1M2M3" in msg_pair or "M1M2M3M4" in msg_pair

    # ------------------------------------------------------------------
    # Clasificación de calidad
    # ------------------------------------------------------------------

    def _classify_quality(self, result: ValidationResult) -> None:
        """Clasifica la calidad del handshake basado en el análisis."""
        score = self._compute_score(result)

        if score >= 0.85:
            result.quality = QualityClassification.EXCELLENT
        elif score >= 0.65:
            result.quality = QualityClassification.GOOD
        elif score >= 0.50:
            result.quality = QualityClassification.ACCEPTABLE
        elif score >= 0.20:
            result.quality = QualityClassification.POOR
        else:
            result.quality = QualityClassification.INVALID

        result.quality_score = score
        result.validated = score >= 0.50

    def _compute_score(self, result: ValidationResult) -> float:
        """Computa un puntaje 0..1 para el handshake."""
        score = 0.75 if result.pmkid.detected else 0.0
        eapol = result.eapol

        pair_scores = {info[0]: info[2] for info in _EAPOL_PAIR_INFO.values()}
        for pair in eapol.pairs_complete:
            score = max(score, pair_scores.get(pair, 0.0))

        # Compatibilidad con resultados descriptivos creados antes del parser 22000.
        if not eapol.pairs_complete and eapol.messages_found:
            legacy_score = 0.0
            if "M1" in eapol.messages_found:
                legacy_score += self._SCORE_M1
            if "M2" in eapol.messages_found:
                legacy_score += self._SCORE_M2
            if "M3" in eapol.messages_found:
                legacy_score += self._SCORE_M3
            if "M4" in eapol.messages_found:
                legacy_score += self._SCORE_M4
            score = max(score, legacy_score)

        # Bonus por handshake completo.
        if eapol.has_full_handshake:
            score = min(score + 0.10, 1.0)

        # Bonus por PMKID + EAPOL juntos.
        if result.pmkid.detected and eapol.has_m12:
            score = min(score + 0.05, 1.0)

        return min(score, 1.0)

    @staticmethod
    def _score_message_pair(message_pair: str | None) -> float:
        if not message_pair or message_pair == "PMKID":
            return 0.75 if message_pair == "PMKID" else 0.0
        try:
            pair_value = int(message_pair, 16) & 0x07
        except ValueError:
            return 0.0
        info = _EAPOL_PAIR_INFO.get(pair_value)
        return info[2] if info else 0.0

    # ------------------------------------------------------------------
    # Ejecución de hcxpcapngtool
    # ------------------------------------------------------------------

    async def _run_hcxpcapngtool(self, input_path: str, output_path: str) -> tuple[str, str]:
        """Ejecuta hcxpcapngtool y retorna (stdout, stderr)."""
        proc = await asyncio.create_subprocess_exec(
            self._tool_path,
            "-o",
            output_path,
            input_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        stdout_text = stdout.decode("utf-8", errors="replace") if stdout else ""
        stderr_text = stderr.decode("utf-8", errors="replace") if stderr else ""

        # Analizar salida para detectar handshake/pmkid.
        combined = stdout_text + stderr_text
        for line in combined.split("\n"):
            self._parse_tool_line(line)

        return stdout_text, stderr_text

    def _parse_tool_line(self, line: str) -> dict[str, Any] | None:
        """Procesa una línea de salida de hcxpcapngtool.

        Usado internamente para detectar eventos en la salida de la herramienta.
        """
        stripped = line.strip()
        if not stripped:
            return None

        result: dict[str, Any] = {}

        if _RE_HANDSHAKE.search(stripped):
            result["handshake_detected"] = True
        if _RE_PMKID.search(stripped):
            result["pmkid_detected"] = True

        # Extraer menciones de mensajes EAPOL.
        eapol_msgs = _RE_EAPOL_MSG.findall(stripped)
        if eapol_msgs:
            result["eapol_messages"] = eapol_msgs

        return result if result else None

    # ------------------------------------------------------------------
    # Persistencia
    # ------------------------------------------------------------------

    def _resolve_source(self, capture: Capture | None, file_path: str | None) -> str | None:
        """Resuelve la ruta del archivo fuente."""
        if file_path:
            return file_path
        if capture and capture.path:
            return capture.path
        return None

    def _find_existing_artifact(
        self, capture: Capture, db_session: Session | None
    ) -> HandshakeArtifact | None:
        """Busca un HandshakeArtifact existente para esta captura."""
        if not db_session:
            return None
        try:
            stmt = select(HandshakeArtifact).where(HandshakeArtifact.capture_id == capture.id)
            return db_session.scalars(stmt).first()
        except Exception:
            return None

    def _persist_artifact(
        self,
        db_session: Session,
        capture: Capture,
        result: ValidationResult,
        hash22000_path: str,
    ) -> HandshakeArtifact:
        """Crea o actualiza un HandshakeArtifact en la BD."""
        quality_map = {
            QualityClassification.EXCELLENT: HandshakeQuality.EXCELLENT,
            QualityClassification.GOOD: HandshakeQuality.GOOD,
            QualityClassification.ACCEPTABLE: HandshakeQuality.ACCEPTABLE,
            QualityClassification.POOR: HandshakeQuality.POOR,
            QualityClassification.INVALID: HandshakeQuality.INVALID,
        }

        access_point_id: int | None = None
        if capture.bssid:
            access_point_id = db_session.scalar(
                select(AccessPoint.id).where(
                    AccessPoint.engagement_id == capture.engagement_id,
                    AccessPoint.bssid == capture.bssid,
                )
            )

        artifact = db_session.scalar(
            select(HandshakeArtifact).where(HandshakeArtifact.capture_id == capture.id)
        )
        if artifact is None:
            artifact = HandshakeArtifact(capture_id=capture.id)
            db_session.add(artifact)

        artifact.access_point_id = access_point_id
        artifact.station_id = None
        artifact.kind = result.kind
        artifact.message_pair = result.message_pair
        artifact.quality = quality_map.get(result.quality, HandshakeQuality.INVALID)
        artifact.validated = result.validated
        artifact.hash22000_path = None
        db_session.commit()
        db_session.refresh(artifact)

        # Copiar el archivo .22000 a data/ sin sobrescribir derivados anteriores.
        if hash22000_path and Path(hash22000_path).is_file():
            persisted_path = self._persist_hashfile(artifact, hash22000_path)
            if persisted_path:
                artifact.hash22000_path = persisted_path
                db_session.commit()
                db_session.refresh(artifact)

        return artifact

    def _persist_hashfile(self, artifact: HandshakeArtifact, temp_path: str) -> str | None:
        """Copia el archivo .22000 temporal a una ubicación permanente."""
        from aegiswifi.core.config import get_settings

        settings = get_settings()
        dest_dir = settings.paths.evidence_dir / "hashes"
        dest_dir.mkdir(parents=True, exist_ok=True)

        dest = dest_dir / f"artifact_{artifact.id}_{uuid.uuid4().hex[:8]}.22000"

        try:
            shutil.copy2(temp_path, str(dest))
            artifact.hash22000_path = str(dest)
            return str(dest)
        except OSError:
            return None

    # ------------------------------------------------------------------
    # Conversión a reporte
    # ------------------------------------------------------------------

    def _artifact_to_result(
        self, artifact: HandshakeArtifact, capture: Capture | None = None
    ) -> ValidationResult:
        """Convierte un HandshakeArtifact existente a ValidationResult."""
        quality_map = {
            HandshakeQuality.EXCELLENT: QualityClassification.EXCELLENT,
            HandshakeQuality.GOOD: QualityClassification.GOOD,
            HandshakeQuality.ACCEPTABLE: QualityClassification.ACCEPTABLE,
            HandshakeQuality.POOR: QualityClassification.POOR,
            HandshakeQuality.INVALID: QualityClassification.INVALID,
        }

        return ValidationResult(
            artifact_id=artifact.id,
            capture_id=capture.id if capture else None,
            quality=quality_map.get(
                HandshakeQuality(artifact.quality),
                QualityClassification.INVALID,
            ),
            validated=artifact.validated,
            hash22000_path=artifact.hash22000_path,
            kind=artifact.kind,
            message_pair=artifact.message_pair,
            source_file=capture.path if capture else None,
        )

    def build_report(self, artifact: HandshakeArtifact) -> dict[str, Any]:
        """Construye un reporte legible desde un artifact."""
        from aegiswifi.validation.schemas import HandshakeReport

        station_mac = None
        if artifact.station:
            station_mac = artifact.station.mac

        crack_status = None
        if artifact.cracking_job:
            crack_status = artifact.cracking_job.status

        report = HandshakeReport(
            id=artifact.id,
            bssid=artifact.access_point.bssid if artifact.access_point else None,
            ssid=artifact.access_point.ssid if artifact.access_point else None,
            channel=artifact.access_point.channel if artifact.access_point else None,
            kind=artifact.kind,
            quality=artifact.quality,
            validated=artifact.validated,
            message_pair=artifact.message_pair,
            hash_file=artifact.hash22000_path,
            crack_status=crack_status,
            access_point_id=artifact.access_point_id,
            station_mac=station_mac,
            created_at=artifact.created_at,
        )
        return report.model_dump()


# Singleton.
_validation_service: HandshakeValidationService | None = None


def get_validation_service() -> HandshakeValidationService:
    """Retorna el singleton del servicio de validación."""
    global _validation_service
    if _validation_service is None:
        _validation_service = HandshakeValidationService()
    return _validation_service
