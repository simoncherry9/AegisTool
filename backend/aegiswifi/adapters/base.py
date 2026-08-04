"""Adaptador base abstracto para herramientas externas (minuta §27).

ToolAdapter define la interfaz que deben implementar todos los adaptadores.
Cada adaptador concreto envuelve :class:`ProcessSupervisor` para la ejecución
del subproceso y normaliza la salida textual de la herramienta.
"""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from typing import Any

from aegiswifi.core.config import JobConfig
from aegiswifi.jobs.event_bus import EventBus
from aegiswifi.jobs.process_supervisor import ProcessSupervisor


class ToolAdapter(ABC):
    """Interfaz base para adaptadores de herramientas externas (minuta §27).

    Cada adaptador concreto debe implementar:
      - :meth:`build_command` — construye la línea de comandos.
      - :meth:`parse_output` — normaliza una línea de stdout.
      - :meth:`collect_results` — retorna resultados estructurados.

    Métodos opcionales a sobrescribir:
      - :meth:`start` — lógica de arranque personalizada.
      - :meth:`validate_installation` — verificación por defecto vía ``which``.
      - :meth:`get_version` — versión por defecto vía ``--version``.
      - :meth:`cleanup` — limpieza final.
    """

    tool_name: str = ""

    def __init__(
        self,
        job_id: int,
        engagement_id: int,
        event_bus: EventBus,
        config: JobConfig,
    ) -> None:
        self._job_id = job_id
        self._engagement_id = engagement_id
        self._event_bus = event_bus
        self._config = config
        self._supervisor: ProcessSupervisor | None = None
        self._results: dict[str, Any] = {}
        self._raw_result: dict[str, Any] = {}
        self._job_parameters: dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Instalación y versión
    # ------------------------------------------------------------------

    async def validate_installation(self) -> bool:
        """Verifica que la herramienta esté instalada vía ``which``."""
        proc = await asyncio.create_subprocess_exec(
            "which",
            self.tool_name,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        code = await proc.wait()
        return code == 0

    async def get_version(self) -> str:
        """Retorna la versión vía ``<tool> --version``."""
        proc = await asyncio.create_subprocess_exec(
            self.tool_name,
            "--version",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        if stdout:
            return stdout.decode("utf-8", errors="replace").split("\n")[0].strip()
        return "unknown"

    # ------------------------------------------------------------------
    # Interfaz abstracta
    # ------------------------------------------------------------------

    @abstractmethod
    async def build_command(self, options: dict[str, Any]) -> list[str]:
        """Construye la lista de argumentos para :func:`create_subprocess_exec`."""
        ...

    @abstractmethod
    async def parse_output(self, line: str) -> dict[str, Any] | None:
        """Procesa una línea de stdout.

        Retorna un dict con datos relevantes si la línea contiene información
        de interés, o ``None`` para líneas triviais.
        """
        ...

    @abstractmethod
    async def collect_results(self) -> dict[str, Any]:
        """Retorna resultados estructurados después de que la herramienta termina."""
        ...

    # ------------------------------------------------------------------
    # Ejecución
    # ------------------------------------------------------------------

    async def start(self, context: dict[str, Any]) -> dict[str, Any]:  # noqa: ASYNC109
        """Ejecuta la herramienta vía :class:`ProcessSupervisor`.

        ``context`` puede contener:
          - ``options`` (dict): parámetros para :meth:`build_command`.
          - ``timeout_seconds`` (int, opcional): timeout de ejecución.
          - ``cwd`` (Path, opcional): directorio de trabajo.
          - ``env`` (dict, opcional): variables de entorno adicionales.
        """
        self._job_parameters = context
        cmd = await self.build_command(context.get("options", {}))
        self._supervisor = ProcessSupervisor(
            job_id=self._job_id,
            engagement_id=self._engagement_id,
            log_dir=self._config.log_dir,
            event_bus=self._event_bus,
            max_memory_lines=self._config.max_log_lines_memory,
        )
        result = await self._supervisor.run(
            cmd,
            timeout_sec=context.get("timeout_seconds"),
            cwd=context.get("cwd"),
            env=context.get("env"),
        )
        self._raw_result = result
        return result

    async def cleanup(self) -> None:
        """Limpieza final del supervisor si quedó abierto."""
        if self._supervisor is not None:
            self._supervisor.cleanup()
