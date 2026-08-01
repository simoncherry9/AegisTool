"""Escáner inalámbrico vía airodump-ng (minuta §14, §37).

Lanza un subproceso de airodump-ng en background, lee el CSV
que escribe periódicamente y notifica al inventario via callback.

Graceful degradation: funciones ``_run_*`` devuelven stdout vacío
si la herramienta no está instalada.
"""

from __future__ import annotations

import asyncio
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from structlog import get_logger

log = get_logger(__name__)


# ── Constantes ──────────────────────────────────────────────────────

_DEFAULT_TIMEOUT = 30.0
_WRITE_INTERVAL = 2  # segundos entre escrituras CSV
_CSV_POLL_INTERVAL = 2.0  # segundos entre polls


from aegiswifi.core.privileged import run_privileged_cmd, spawn_privileged_process


# ── Scanner ─────────────────────────────────────────────────────────


class AirodumpScanner:
    """Escáner que lanza airodump-ng y monitorea su salida CSV.

    Attributes:
        interface:  Interfaz en monitor mode.
        on_update:  Callable invoked con ``(aps, clients)`` en cada
                    actualización CSV.
        running:    ``True`` mientras el escáner esté activo.
    """

    def __init__(
        self,
        interface: str,
        on_update: Callable[[list[dict[str, Any]], list[dict[str, Any]]], None] | None = None,
        output_dir: str | Path | None = None,
    ) -> None:
        self.interface = interface
        self.on_update = on_update
        self.running = False

        self._output_dir = Path(output_dir) if output_dir else Path(tempfile.mkdtemp(prefix="airodump_"))
        self._output_prefix = str(self._output_dir / "capture")
        self._process: asyncio.subprocess.Process | None = None
        self._poll_task: asyncio.Task[None] | None = None
        self._channel: int | None = None
        self._started_at: float | None = None

    async def start(self, *, channel: int | None = None) -> bool:
        """Inicia airodump-ng en background con privilegios sudo/root."""
        self._started_at = asyncio.get_event_loop().time()

        args = [
            "airodump-ng",
            self.interface,
            "--write", self._output_prefix,
            "--write-interval", str(_WRITE_INTERVAL),
            "--output-format", "csv",
        ]
        if channel is not None:
            args.extend(["--channel", str(channel)])
            self._channel = channel

        self._process = await self._spawn_process(args)

        if self._process is None:
            log.error("failed to start airodump-ng", interface=self.interface)
            return False

        self.running = True
        self._poll_task = asyncio.create_task(self._poll_csv())
        log.info("airodump-ng started", interface=self.interface, prefix=self._output_prefix)
        return True

    async def stop(self) -> None:
        """Detiene el escáner y limpia recursos."""
        self.running = False

        if self._poll_task is not None:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
            self._poll_task = None

        if self._process is not None:
            try:
                self._process.terminate()
                await asyncio.wait_for(self._process.wait(), timeout=5.0)
            except Exception:
                if self._process is not None:
                    self._process.kill()
                    try:
                        await self._process.wait()
                    except Exception:
                        pass
            self._process = None

        log.info("airodump-ng stopped", interface=self.interface)

    async def set_channel(self, channel: int) -> None:
        """Cambia el canal de escaneo."""
        was_running = self.running
        if was_running:
            await self.stop()

        self._channel = channel

        if was_running:
            await self.start(channel=channel)

    @property
    def uptime_seconds(self) -> int | None:
        if self._started_at is None:
            return None
        return int(asyncio.get_event_loop().time() - self._started_at)

    # ── Internals ───────────────────────────────────────────────────

    async def _spawn_process(
        self,
        args: list[str],
    ) -> asyncio.subprocess.Process | None:
        """Spawn del subproceso airodump-ng con sudo/root."""
        process = await spawn_privileged_process(args)
        if process is None:
            log.error("airodump-ng spawn failed", interface=self.interface)
            return None
        return process

    async def _poll_csv(self) -> None:
        """Poll del archivo CSV cada N segundos mientras corre."""
        csv_path = Path(f"{self._output_prefix}-01.csv")

        while self.running:
            try:
                await asyncio.sleep(_CSV_POLL_INTERVAL)

                if not csv_path.exists():
                    continue

                content = csv_path.read_text(encoding="utf-8", errors="replace")
                if not content.strip():
                    continue

                aps, clients = await _parse_csv_content(content)

                if self.on_update and (aps or clients):
                    self.on_update(aps, clients)

            except asyncio.CancelledError:
                break
            except Exception as exc:
                log.warning("csv poll error", error=str(exc))


# ── Funciones de utilidad ───────────────────────────────────────────


async def _run_airodump(args: list[str], timeout: float = _DEFAULT_TIMEOUT) -> tuple[str, str]:
    """Ejecuta airodump-ng y captura su salida.

    Esta función es intencionalmente simple para ser mockeable en tests.
    En el scanner real no se usa (el proceso corre en background).

    Returns:
        ``(stdout, stderr)``. Vacío si falla.
    """
    try:
        process = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=timeout,
        )
        return stdout.decode("utf-8", errors="replace"), stderr.decode("utf-8", errors="replace")
    except (TimeoutError, FileNotFoundError, OSError):
        return "", ""


async def _scan_available() -> bool:
    """Verifica si airodump-ng está instalado."""
    stdout, stderr = await _run_airodump(["--version"])
    return bool("airodump-ng" in stdout.lower() or "airodump-ng" in stderr.lower())


async def _parse_csv_content(content: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Parse CSV content into AP and client dicts.

    Avoids circular import with csv_parser module by inlining
    a minimal parser here for the polling path.
    """
    from aegiswifi.discovery.csv_parser import parse_full_csv

    return parse_full_csv(content)