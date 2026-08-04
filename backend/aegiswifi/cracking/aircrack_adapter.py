"""Adaptador ToolAdapter para Aircrack-ng (minuta §18, §27).

Aircrack-ng crackea el handshake WPA/WPA2 directamente desde el archivo
``.cap`` original (sin necesidad de convertir a ``.22000``), ejecutando un
ataque de diccionario en CPU. Es la opción preferida cuando no hay GPU
disponible (p. ej. una VM), por lo que el planificador lo coloca antes que
las etapas de hashcat.

Se registra con el tipo ``aircrack_crack`` en el :mod:`registry <aegiswifi.adapters.registry>`.
"""

from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import Any

from aegiswifi.adapters.base import ToolAdapter
from aegiswifi.adapters.registry import register_adapter

# "KEY FOUND! [ password ]" — aircrack-ng imprime la clave entre corchetes.
_KEY_FOUND_RE = re.compile(r"KEY\s+FOUND!\s*\[\s*([^\]]+)\s*\]")


class AircrackNgAdapter(ToolAdapter):
    """Adaptador concreto para aircrack-ng (ataque por diccionario).

    Parámetros esperados en ``options``:
      - ``cap_file`` (str, obligatorio): ruta al archivo .cap.
      - ``bssid`` (str, obligatorio): BSSID del AP objetivo.
      - ``dictionary`` (str, opcional): ruta a la wordlist.
      - ``essid`` (str, opcional): ESSID para filtrado adicional.
    """

    tool_name = "aircrack-ng"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._cracked_password: str | None = None

    # ------------------------------------------------------------------
    # Instalación y versión
    # ------------------------------------------------------------------

    async def get_version(self) -> str:
        proc = await asyncio.create_subprocess_exec(
            "aircrack-ng",
            "--help",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        text = (stdout + stderr).decode("utf-8", errors="replace")
        for line in text.split("\n"):
            if "version" in line.lower():
                return line.strip()
        return "aircrack-ng (version unknown)"

    # ------------------------------------------------------------------
    # Construcción del comando
    # ------------------------------------------------------------------

    async def build_command(self, options: dict[str, Any]) -> list[str]:
        """Construye el comando de aircrack-ng para ataque de diccionario."""
        cap_file: str = options["cap_file"]
        bssid: str = options["bssid"]

        cmd: list[str] = ["aircrack-ng", "-a", "2", "-b", bssid]
        if dict_path := options.get("dictionary"):
            cmd.extend(["-w", dict_path])
        if essid := options.get("essid"):
            cmd.extend(["-e", essid])
        cmd.append(cap_file)
        return cmd

    # ------------------------------------------------------------------
    # Parseo de salida en vivo
    # ------------------------------------------------------------------

    async def parse_output(self, line: str) -> dict[str, Any] | None:
        """Detecta la línea ``KEY FOUND! [ password ]`` de aircrack-ng."""
        match = _KEY_FOUND_RE.search(line)
        if match:
            self._cracked_password = match.group(1).strip()
            return {
                "event": "password_cracked",
                "password": self._cracked_password,
                "raw": line,
            }
        return None

    # ------------------------------------------------------------------
    # Resultados finales
    # ------------------------------------------------------------------

    async def collect_results(self) -> dict[str, Any]:
        """Retorna resultados estructurados post-ejecución.

        Aircrack-ng sale con código 0 incluso cuando la clave no se
        encuentra ("Failed to find the key"); un código distinto de 0
        indica un error real (archivo .cap ilegible, wordlist inexistente,
        argumentos inválidos). Los errores NO se reportan como "exhausted".
        """
        raw = self._raw_result
        exit_code = raw.get("exit_code")

        password = self._cracked_password
        if password is None:
            password = self._extract_password_from_log()

        error = exit_code not in (0, None)
        error_message = self._extract_error_message(exit_code) if error else None

        return {
            "cracked": password is not None,
            "password": password,
            "exit_code": exit_code,
            "error": error,
            "error_message": error_message,
            "peak_speed": 0,
            "stages_executed": 1,
            "total_runtime_seconds": raw.get("runtime_seconds"),
            "log_path": raw.get("log_path"),
            "sha256": raw.get("sha256"),
        }

    def _extract_password_from_log(self) -> str | None:
        """Busca ``KEY FOUND!`` en el log si ``parse_output`` no lo capturó."""
        log_path = self._raw_result.get("log_path")
        if not log_path:
            return None
        try:
            lines = Path(log_path).read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            return None
        for line in lines:
            match = _KEY_FOUND_RE.search(line)
            if match:
                return match.group(1).strip()
        return None

    def _extract_error_message(self, exit_code: int | None) -> str:
        """Devuelve un mensaje legible cuando aircrack-ng termina con error."""
        log_path = self._raw_result.get("log_path")
        if log_path:
            try:
                lines = Path(log_path).read_text(
                    encoding="utf-8", errors="replace"
                ).splitlines()
            except OSError:
                lines = []
            interesting = [line.strip() for line in lines if line.strip()]
            if interesting:
                return " | ".join(interesting[-3:])
        return f"aircrack-ng terminó con código de salida {exit_code}"


# --- Registro automático al importar el módulo -----------------------------

register_adapter("aircrack_crack", AircrackNgAdapter)
