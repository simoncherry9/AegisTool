"""Almacenamiento de evidencia en disco con hash SHA-256 (minuta §30).

:class:`EvidenceStore` se encarga de:
  1. Copiar archivos de origen al directorio de evidencia.
  2. Calcular SHA-256 durante la copia (streaming).
  3. Crear el registro :class:`Capture` en la base de datos.
  4. Garantizar inmutabilidad lógica (no sobrescritura).
"""

from __future__ import annotations

import asyncio
import hashlib
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from aegiswifi.database.models import Capture


class EvidenceStore:
    """Servicio de almacenamiento de evidencia en disco + BD.

    Args:
        evidence_dir: Directorio raíz para evidencia.
        session_factory: Callable que retorna una sesión SQLAlchemy sync.
    """

    def __init__(
        self,
        evidence_dir: Path,
        session_factory: Callable[[], Session],
    ) -> None:
        self._evidence_dir = evidence_dir
        self._session_factory = session_factory

    async def store_artifact(
        self,
        *,
        source_path: Path,
        original_filename: str,
        engagement_id: int,
        job_id: int,
        category: str = "original",
        format: str = "pcapng",
        tool: str = "",
        tool_version: str | None = None,
        interface: str | None = None,
        channel: int | None = None,
        bssid: str | None = None,
        ssid: str | None = None,
        metadata: dict[str, Any] | None = None,
        derived_from_id: int | None = None,
    ) -> Capture:
        """Almacena un archivo como evidencia.

        1. Calcula SHA-256 haciendo streaming del archivo.
        2. Copia el archivo a ``evidence_dir/{engagement_id}/{job_id}/{category}/``.
        3. Inserta el registro en BD y retorna el objeto :class:`Capture`.
        """
        # --- Calcular SHA-256 y copiar a destino ---
        dest_dir = self._evidence_dir / str(engagement_id) / str(job_id) / category
        dest_path = dest_dir / original_filename

        sha256_hex, size_bytes = await asyncio.to_thread(
            self._copy_with_hash, source_path, dest_path
        )

        # --- Crear registro en BD ---
        def _create_db() -> Capture:
            session = self._session_factory()
            try:
                capture = Capture(
                    engagement_id=engagement_id,
                    job_id=job_id,
                    category=category,
                    path=str(dest_path),
                    format=format,
                    sha256=sha256_hex,
                    original_filename=original_filename,
                    size_bytes=size_bytes,
                    interface=interface,
                    channel=channel,
                    bssid=bssid,
                    ssid=ssid,
                    tool=tool,
                    tool_version=tool_version,
                    extra_metadata=metadata or {},
                    derived_from_id=derived_from_id,
                    started_at=datetime.now(UTC),
                )
                session.add(capture)
                session.commit()
                session.refresh(capture)
                return capture
            finally:
                session.close()

        return await asyncio.to_thread(_create_db)

    # ------------------------------------------------------------------
    # Internos
    # ------------------------------------------------------------------

    def _copy_with_hash(self, source: Path, dest: Path) -> tuple[str, int]:
        """Copia ``source`` a ``dest`` calculando SHA-256 en streaming.

        Lanza :class:`FileExistsError` si ``dest`` ya existe (inmutabilidad).
        """
        if dest.exists():
            raise FileExistsError(f"el archivo de evidencia ya existe (inmutabilidad): {dest}")
        dest.parent.mkdir(parents=True, exist_ok=True)

        sha256 = hashlib.sha256()
        size = 0

        with source.open("rb") as src_fp, dest.open("wb") as dst_fp:
            while True:
                chunk = src_fp.read(65536)  # 64 KiB
                if not chunk:
                    break
                sha256.update(chunk)
                dst_fp.write(chunk)
                size += len(chunk)

        return sha256.hexdigest(), size

    @staticmethod
    def verify_integrity(file_path: Path, expected_sha256: str) -> bool:
        """Verifica que un archivo tenga el SHA-256 esperado."""
        sha256 = hashlib.sha256()
        with file_path.open("rb") as fp:
            while True:
                chunk = fp.read(65536)
                if not chunk:
                    break
                sha256.update(chunk)
        return sha256.hexdigest() == expected_sha256
