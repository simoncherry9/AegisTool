"""Adaptadores concretos para herramientas externas (minuta §27).

Adaptadores iniciales:
  - :class:`PassiveCaptureAdapter`  → tcpdump
  - :class:`HandshakeCaptureAdapter` → airodump-ng
  - :class:`PMKIDCaptureAdapter` → hcxdumptool
  - :class:`HcxPcapngToolAdapter` → hcxpcapngtool

Cada adaptador se registra automáticamente al importar el módulo.
"""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from typing import Any

from aegiswifi.adapters.base import ToolAdapter
from aegiswifi.adapters.registry import register_adapter


class PassiveCaptureAdapter(ToolAdapter):
    """Captura pasiva de tráfico en una interfaz (tcpdump).

    Trabaja con ``job.kind = "passive_capture"``.

    Parámetros esperados en ``job.parameters``:
      - ``interface`` (str, obligatorio): nombre de la interfaz.
      - ``channel`` (int, opcional): canal a monitorizar.
      - ``output`` (str, opcional): ruta del archivo de captura.
      - ``duration`` (int, opcional): segundos de captura.
    """

    tool_name = "tcpdump"

    async def build_command(self, options: dict[str, Any]) -> list[str]:
        output = options.get("output", str(_TMP / f"passive_{self._job_id}.pcapng"))
        interface = options["interface"]
        cmd = [
            "tcpdump",
            "-i",
            interface,
            "-w",
            output,
            "-s",
            "0",
            "-U",
            "not",
            "port",
            "22",
        ]
        return cmd

    async def parse_output(self, line: str) -> dict[str, Any] | None:
        # tcpdump no produce salida estructurada en modo -w; contamos líneas
        # de metadata en stderr.
        if "packets captured" in line:
            return {"packets_captured": line.strip()}
        return None

    async def collect_results(self) -> dict[str, Any]:
        raw = self._raw_result
        return {
            "exit_code": raw.get("exit_code"),
            "line_count": raw.get("line_count"),
            "log_path": raw.get("log_path"),
            "sha256": raw.get("sha256"),
        }


class HandshakeCaptureAdapter(ToolAdapter):
    """Captura de handshake EAPOL vía airodump-ng.

    Trabaja con ``job.kind = "handshake_capture"``.

    Parámetros esperados en ``job.parameters``:
      - ``interface`` (str, obligatorio): interfaz en modo monitor.
      - ``bssid`` (str, obligatorio): BSSID del AP objetivo.
      - ``channel`` (int, opcional): canal del AP.
      - ``output_prefix`` (str, opcional): prefijo para archivos de salida.
    """

    tool_name = "airodump-ng"

    async def validate_installation(self) -> bool:
        proc = await asyncio.create_subprocess_exec(
            "which",
            "airodump-ng",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        return (await proc.wait()) == 0

    async def get_version(self) -> str:
        proc = await asyncio.create_subprocess_exec(
            "airodump-ng",
            "--help",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        text = (stdout + stderr).decode("utf-8", errors="replace")
        for line in text.split("\n"):
            if "version" in line.lower():
                return line.strip()
        return "airodump-ng (version unknown)"

    async def build_command(self, options: dict[str, Any]) -> list[str]:
        interface = options["interface"]
        bssid = options["bssid"]
        channel = options.get("channel")
        output_prefix = options.get("output_prefix", str(_TMP / f"handshake_{self._job_id}"))

        cmd = [
            "airodump-ng",
            "-i",
            interface,
            "-w",
            output_prefix,
            "--bssid",
            bssid,
            "--write-interval",
            "1",
        ]
        if channel:
            cmd.extend(["-c", str(channel)])
        return cmd

    async def parse_output(self, line: str) -> dict[str, Any] | None:
        if "WPA handshake" in line:
            return {"handshake_detected": True, "raw": line.strip()}
        return None

    async def collect_results(self) -> dict[str, Any]:
        raw = self._raw_result
        return {
            "exit_code": raw.get("exit_code"),
            "line_count": raw.get("line_count"),
            "log_path": raw.get("log_path"),
            "sha256": raw.get("sha256"),
        }


class PMKIDCaptureAdapter(ToolAdapter):
    """Captura de PMKID vía hcxdumptool.

    Trabaja con ``job.kind = "pmkid_capture"``.

    Parámetros esperados en ``job.parameters``:
      - ``interface`` (str, obligatorio): interfaz en modo monitor.
      - ``channel`` (int, opcional): canal a escuchar.
      - ``output`` (str, opcional): ruta del archivo de salida.
    """

    tool_name = "hcxdumptool"

    async def validate_installation(self) -> bool:
        proc = await asyncio.create_subprocess_exec(
            "which",
            "hcxdumptool",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        return (await proc.wait()) == 0

    async def get_version(self) -> str:
        proc = await asyncio.create_subprocess_exec(
            "hcxdumptool",
            "--version",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        if stdout:
            return stdout.decode("utf-8", errors="replace").split("\n")[0].strip()
        return "hcxdumptool (version unknown)"

    async def build_command(self, options: dict[str, Any]) -> list[str]:
        interface = options["interface"]
        output = options.get("output", str(_TMP / f"pmkid_{self._job_id}.pcapng"))
        channel = options.get("channel")

        cmd = [
            "hcxdumptool",
            "-i",
            interface,
            "-o",
            output,
            "--enable_status=1",
        ]
        if channel:
            cmd.extend(["-c", str(channel)])
        return cmd

    async def parse_output(self, line: str) -> dict[str, Any] | None:
        if "PMKID" in line or "FOUND" in line:
            return {"pmkid_event": True, "raw": line.strip()}
        return None

    async def collect_results(self) -> dict[str, Any]:
        raw = self._raw_result
        return {
            "exit_code": raw.get("exit_code"),
            "line_count": raw.get("line_count"),
            "log_path": raw.get("log_path"),
            "sha256": raw.get("sha256"),
        }


class HcxPcapngToolAdapter(ToolAdapter):
    """Conversión de PCAPNG a hash 22000 vía hcxpcapngtool.

    Trabaja con ``job.kind = "hash_convert"``.

    Parámetros esperados en ``job.parameters``:
      - ``input`` (str, obligatorio): ruta del archivo PCAP/PCAPNG de entrada.
      - ``output`` (str, opcional): ruta del archivo 22000 de salida.
    """

    tool_name = "hcxpcapngtool"

    async def validate_installation(self) -> bool:
        proc = await asyncio.create_subprocess_exec(
            "which",
            "hcxpcapngtool",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        return (await proc.wait()) == 0

    async def get_version(self) -> str:
        proc = await asyncio.create_subprocess_exec(
            "hcxpcapngtool",
            "--version",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        if stdout:
            return stdout.decode("utf-8", errors="replace").split("\n")[0].strip()
        return "hcxpcapngtool (version unknown)"

    async def build_command(self, options: dict[str, Any]) -> list[str]:
        input_path = options["input"]
        output = options.get("output", str(_TMP / f"hashes_{self._job_id}.22000"))
        return ["hcxpcapngtool", "-o", output, input_path]

    async def parse_output(self, line: str) -> dict[str, Any] | None:
        if "written" in line.lower():
            return {"write_event": True, "raw": line.strip()}
        if "pmkid" in line.lower():
            return {"pmkid_detected": True, "raw": line.strip()}
        if "handshake" in line.lower():
            return {"handshake_detected": True, "raw": line.strip()}
        return None

    async def collect_results(self) -> dict[str, Any]:
        raw = self._raw_result
        return {
            "exit_code": raw.get("exit_code"),
            "line_count": raw.get("line_count"),
            "log_path": raw.get("log_path"),
            "sha256": raw.get("sha256"),
        }


# --- Registro automático al importar el módulo -----------------------------

register_adapter("passive_capture", PassiveCaptureAdapter)
register_adapter("handshake_capture", HandshakeCaptureAdapter)
register_adapter("pmkid_capture", PMKIDCaptureAdapter)
register_adapter("hash_convert", HcxPcapngToolAdapter)

# Ruta de temp compartida por todos los adaptadores.
_TMP = Path(tempfile.gettempdir())
