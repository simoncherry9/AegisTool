"""Servicio de validación de handshakes (minuta §15, §16, §28).

Analiza capturas en busca de handshakes EAPOL y PMKID mediante
hcxpcapngtool, clasifica la calidad y persiste los resultados en
:class:`HandshakeArtifact <aegiswifi.database.models.HandshakeArtifact>`.
"""

from __future__ import annotations

import asyncio
import os
import re
import tempfile
from pathlib import Path
from typing import Any

from aegiswifi.database.models import (
    Capture,
    HandshakeArtifact,
    HandshakeQuality,
)
from aegiswifi.validation.schemas import (
    EapolAnalysis,
    PmkidAnalysis,
    QualityClassification,
    ValidationResult,
)

# Regex para detectar líneas de output de hcxpcapngtool.
_RE_HANDSHAKE = re.compile(r"handshake", re.IGNORECASE)
_RE_PMKID = re.compile(r"pmkid", re.IGNORECASE)
_RE_WRITTEN = re.compile(r"written", re.IGNORECASE)
_RE_EAPOL_MSG = re.compile(r"(M[1-4])", re.IGNORECASE)


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
            stdout, stderr = await self._run_hcxpcapngtool(
                str(source_path), output_path
            )

            result.tool_output = (stdout + stderr)[:2000]

            if not Path(output_path).is_file() or os.path.getsize(output_path) == 0:
                result.errors.append(
                    "hcxpcapngtool no generó archivo de salida"
                )
                return result

            # Analizar el archivo .22000 generado.
            self._analyze_hashfile(Path(output_path), result)

            # Clasificar calidad.
            self._classify_quality(result)

            # Persistir artifact en BD si tenemos sesión y capture.
            if db_session and capture:
                artifact = self._persist_artifact(
                    db_session, capture, result, output_path
                )
                result.artifact_id = artifact.id

            return result

        except FileNotFoundError:
            result.errors.append(
                "hcxpcapngtool no está instalado en el sistema"
            )
            return result
        except Exception as exc:
            result.errors.append(f"Error durante validación: {exc}")
            return result
        finally:
            # Limpiar archivo temporal si no se persiste.
            if not result.artifact_id and Path(output_path).exists():
                os.unlink(output_path)

    # ------------------------------------------------------------------
    # Análisis del hash 22000
    # ------------------------------------------------------------------

    def _analyze_hashfile(
        self, hash_path: Path, result: ValidationResult
    ) -> None:
        """Analiza el archivo .22000 generado por hcxpcapngtool.

        El formato 22000 para WPA es::

            WPA*01*message_pair*bssid*station*essid*...
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

        Formato esperado::

            WPA*01*message_pair_hash*bssid*station*essid*...
        """
        if not line.startswith("WPA"):
            return

        fields = line.split("*")
        if len(fields) < 6:
            return

        # message_pair indica qué mensajes EAPOL se capturaron.
        msg_pair = fields[2] if len(fields) > 2 else ""
        bssid = fields[3] if len(fields) > 3 else ""
        station = fields[4] if len(fields) > 4 else ""
        essid_section = fields[5] if len(fields) > 5 else ""

        # Limpiar essid (puede venir con prefijo).
        essid = essid_section.rstrip("*").strip()

        # Actualizar resultado con info encontrada.
        result.kind = "eapol"
        if not result.eapol.has_full_handshake:
            result.eapol.has_full_handshake = self._is_full_handshake(msg_pair)
        if not result.eapol.has_m12:
            result.eapol.has_m12 = "M1M2" in msg_pair or "02" in msg_pair
        if not result.eapol.has_m14:
            result.eapol.has_m14 = "M1M4" in msg_pair or "04" in msg_pair

        if msg_pair and msg_pair not in result.eapol.pairs_complete:
            result.eapol.pairs_complete.append(msg_pair)

        # Almacenar mejor mensaje de par.
        if not result.message_pair or len(msg_pair) > len(result.message_pair or ""):
            result.message_pair = msg_pair

    def _is_full_handshake(self, msg_pair: str) -> bool:
        """Determina si el par de mensajes representa un handshake completo.

        Handshake completo = al menos M1+M2+M3, detectado como 03 (M3 presente).
        """
        return "03" in msg_pair or "M1M3" in msg_pair

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
        score = 0.0
        eapol = result.eapol
        pmkid = result.pmkid

        # Puntaje por mensajes EAPOL.
        if "M1" in eapol.messages_found or "01" in str(eapol.pairs_complete):
            score += self._SCORE_M1
        if "M2" in eapol.messages_found or "02" in str(eapol.pairs_complete):
            score += self._SCORE_M2
        if "M3" in eapol.messages_found or "03" in str(eapol.pairs_complete):
            score += self._SCORE_M3
        if "M4" in eapol.messages_found or "04" in str(eapol.pairs_complete):
            score += self._SCORE_M4

        # Puntaje por PMKID.
        if pmkid.detected:
            score += self._SCORE_PMKID

        # Bonus por handshake completo.
        if eapol.has_full_handshake:
            score = min(score + 0.10, 1.0)

        # Bonus por PMKID + EAPOL juntos.
        if pmkid.detected and eapol.has_m12:
            score = min(score + 0.05, 1.0)

        return min(score, 1.0)

    # ------------------------------------------------------------------
    # Ejecución de hcxpcapngtool
    # ------------------------------------------------------------------

    async def _run_hcxpcapngtool(
        self, input_path: str, output_path: str
    ) -> tuple[str, str]:
        """Ejecuta hcxpcapngtool y retorna (stdout, stderr)."""
        proc = await asyncio.create_subprocess_exec(
            self._tool_path,
            "-o", output_path,
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

    def _resolve_source(
        self, capture: Capture | None, file_path: str | None
    ) -> str | None:
        """Resuelve la ruta del archivo fuente."""
        if file_path:
            return file_path
        if capture and capture.path:
            return capture.path
        return None

    def _find_existing_artifact(
        self, capture: Capture, db_session: Any
    ) -> HandshakeArtifact | None:
        """Busca un HandshakeArtifact existente para esta captura."""
        if not db_session:
            return None
        try:
            from sqlalchemy import select

            stmt = select(HandshakeArtifact).where(
                HandshakeArtifact.capture_id == capture.id
            )
            return db_session.scalars(stmt).first()
        except Exception:
            return None

    def _persist_artifact(
        self,
        db_session: Any,
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

        artifact = HandshakeArtifact(
            capture_id=capture.id,
            access_point_id=None,
            station_id=None,
            kind=result.kind,
            message_pair=result.message_pair,
            quality=quality_map.get(result.quality, HandshakeQuality.INVALID),
            validated=result.validated,
            hash22000_path=hash22000_path,
        )
        db_session.add(artifact)
        db_session.commit()
        db_session.refresh(artifact)

        # Copiar el archivo .22000 a data/ para persistencia.
        self._persist_hashfile(artifact, hash22000_path)

        return artifact

    def _persist_hashfile(
        self, artifact: HandshakeArtifact, temp_path: str
    ) -> str | None:
        """Copia el archivo .22000 temporal a una ubicación permanente."""
        from aegiswifi.core.config import get_settings

        settings = get_settings()
        dest_dir = settings.paths.evidence_dir / "hashes"
        dest_dir.mkdir(parents=True, exist_ok=True)

        dest = dest_dir / f"artifact_{artifact.id}.22000"
        import shutil

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

    def build_report(
        self, artifact: HandshakeArtifact
    ) -> dict[str, Any]:
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
