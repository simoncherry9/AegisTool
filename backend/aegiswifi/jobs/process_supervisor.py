"""Supervisor de procesos externos (minuta §27).

Gestiona subprocesos de herramientas externas vía ``asyncio.create_subprocess_exec``:

  - Stream de stdout/stderr línea por línea.
  - Buffer en memoria hasta un umbral, luego spílla a disco.
  - Emisión de eventos ``job_log_line`` por el EventBus.
  - Graceful shutdown (SIGTERM → SIGKILL).
  - Cálculo de SHA-256 del log al finalizar.

En Fase 1 es un framework listo para usar, pero el JobManager aún usa un placeholder.
Se conectará cuando existan los ToolAdapters (Fase 2+).
"""

from __future__ import annotations

import asyncio
import hashlib
from contextlib import suppress
from pathlib import Path
from typing import Any

from aegiswifi.jobs.event_bus import EventBus, JobEventEnvelope


class ProcessSupervisor:
    """Ejecuta y monitorea un subproceso, emitiendo eventos en tiempo real."""

    def __init__(
        self,
        job_id: int,
        engagement_id: int,
        log_dir: Path,
        event_bus: EventBus,
        max_memory_lines: int = 10000,
    ) -> None:
        self._job_id = job_id
        self._engagement_id = engagement_id
        self._log_dir = log_dir
        self._event_bus = event_bus
        self._max_memory_lines = max_memory_lines

        self._process: asyncio.subprocess.Process | None = None
        self._log_path: Path | None = None
        self._log_file: Any = None  # Buffered text writer
        self._line_count = 0
        self._sha256 = hashlib.sha256()

    async def run(
        self,
        args: list[str],
        *,
        timeout_sec: int | None = None,  # noqa: ASYNC109 — timeout parameter for subprocess
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Ejecuta un subproceso, emite líneas por EventBus y escribe a disco si es necesario.

        Retorna un dict con: exit_code, log_path, sha256, line_count.
        """
        self._log_path = self._log_dir / f"job_{self._job_id}.log"
        self._log_dir.mkdir(parents=True, exist_ok=True)
        self._log_file = self._log_path.open("w", encoding="utf-8")

        try:
            self._process = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=cwd,
                env=env,
            )

            async def _read_stream() -> None:
                if self._process is None or self._process.stdout is None:
                    return
                while True:
                    line_bytes = await self._process.stdout.readline()
                    if not line_bytes:
                        break
                    line = line_bytes.decode("utf-8", errors="replace").rstrip("\n")
                    self._log_file.write(line + "\n")
                    self._log_file.flush()
                    self._sha256.update(line.encode("utf-8") + b"\n")
                    self._line_count += 1

                    if self._line_count <= self._max_memory_lines:
                        self._emit_log_line(line)

            if timeout_sec is not None:
                try:
                    async with asyncio.timeout(timeout_sec):
                        await asyncio.gather(_read_stream(), self._process.wait())
                except TimeoutError:
                    await self.graceful_shutdown()
                    raise
            else:
                await asyncio.gather(_read_stream(), self._process.wait())

        finally:
            if self._log_file is not None:
                self._log_file.close()

        exit_code = self._process.returncode if self._process else -1
        sha256_hex = self._sha256.hexdigest()

        return {
            "exit_code": exit_code,
            "log_path": str(self._log_path),
            "sha256": sha256_hex,
            "line_count": self._line_count,
        }

    async def graceful_shutdown(self, kill_after: float = 5.0) -> None:
        """Detiene el subproceso: SIGTERM + espera, luego SIGKILL."""
        if self._process is None or self._process.returncode is not None:
            return
        try:
            self._process.terminate()
            await asyncio.wait_for(self._process.wait(), timeout=kill_after)
        except TimeoutError:
            self._process.kill()
            await self._process.wait()

    def cleanup(self) -> None:
        """Limpieza final: cierra handles si quedaron abiertos."""
        if self._log_file is not None:
            with suppress(Exception):
                self._log_file.close()
        if self._process is not None and self._process.returncode is None:
            self._process.kill()

    def _emit_log_line(self, line: str) -> None:
        envelope = JobEventEnvelope(
            event_type="job_log_line",
            job_id=self._job_id,
            engagement_id=self._engagement_id,
            data={"line": line, "line_number": self._line_count},
        )
        self._event_bus.publish(envelope)
