"""Adaptador ToolAdapter para Hashcat (minuta §18, §27).

Gestiona la ejecución de hashcat con monitoreo en vivo vía ``--status-json``,
parsea el progreso y expone los resultados estructurados.

Se registra con el tipo ``password_audit`` en el :mod:`registry <aegiswifi.adapters.registry>`.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from aegiswifi.adapters.base import ToolAdapter
from aegiswifi.cracking.schemas import AttackMode, CrackingProgress

# Regex para detectar líneas JSON de status hashcat.
_JSON_STATUS_RE = re.compile(r"^\s*\{")

# Prefijos de líneas de log de hashcat (stderr).
_HASHCAT_LOG_PREFIXES = {
    "Session.Name:", "Status:", "Input.Mode:", "Hash.Target:", "Guess.",
    "Speed.", "Progress.", "Started.", "Time.",
}


class HashcatAdapter(ToolAdapter):
    """Adaptador concreto para hashcat.

    Parámetros esperados en ``job.parameters``:
      - ``hash_file`` (str, obligatorio): ruta al archivo .22000.
      - ``hash_mode`` (int, opcional): modo hash (default 22000).
      - ``attack_mode`` (AttackMode, opcional): modo de ataque.
      - ``dictionary`` (str, opcional): ruta a wordlist.
      - ``rules`` (str, opcional): ruta a reglas.
      - ``mask`` (str, opcional): máscara p. ej. ``?l?l?l?l?d?d``.
      - ``custom_charset_1`` / ``custom_charset_2`` (str, opcional).
      - ``extra_args`` (list[str], opcional): args adicionales.
      - ``workload_profile`` (int, opcional): ``-w`` (default 2).
      - ``opencl_device`` (str, opcional): ``--opencl-device``.
      - ``skip_self_test`` (bool): ``--self-test-disable``.
    """

    tool_name = "hashcat"

    def __init__(self, **kwargs: Any) -> None:
        self._progress_callback: Callable[[CrackingProgress], None] | None = kwargs.pop(
            "progress_callback", None
        )
        super().__init__(**kwargs)
        self._progress: list[CrackingProgress] = []
        self._cracked_password: str | None = None
        output = tempfile.NamedTemporaryFile(prefix="aegis_hashcat_", suffix=".out", delete=False)
        output.close()
        os.chmod(output.name, 0o600)
        self._password_output_path = Path(output.name)

    # ------------------------------------------------------------------
    # Instalación y versión
    # ------------------------------------------------------------------

    async def get_version(self) -> str:
        proc = await asyncio.create_subprocess_exec(
            "hashcat",
            "--version",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        if stdout:
            return stdout.decode("utf-8", errors="replace").split("\n")[0].strip()
        return "hashcat (version unknown)"

    # ------------------------------------------------------------------
    # Construcción del comando
    # ------------------------------------------------------------------

    async def build_command(self, options: dict[str, Any]) -> list[str]:
        """Construye la línea de comandos de hashcat.

        La salida estructurada (status JSON) se envía a stderr; el
        :class:`ProcessSupervisor` la redirige a stdout (``stderr=STDOUT``)
        y el :meth:`parse_output` la detecta vía ``_JSON_STATUS_RE``.
        """
        hash_file: str = options["hash_file"]
        hash_mode: int = options.get("hash_mode", 22000)
        attack_mode_raw = options.get("attack_mode", AttackMode.DICTIONARY)
        attack_mode = (
            AttackMode(attack_mode_raw)
            if isinstance(attack_mode_raw, str)
            else attack_mode_raw
        )

        _MODE_FLAG = {
            AttackMode.DICTIONARY: "0",
            AttackMode.COMBIATOR: "1",
            AttackMode.MASK: "3",
            AttackMode.HYBRID_WORDLIST_MASK: "6",
            AttackMode.HYBRID_MASK_WORDLIST: "7",
            AttackMode.BRUTE_FORCE: "3",
            AttackMode.PRINCE: "0",
            AttackMode.RULE_BASED: "0",
        }

        cmd: list[str] = [
            "hashcat",
            "-m",
            str(hash_mode),
            "-a",
            _MODE_FLAG.get(attack_mode, "0"),
            hash_file,
            "--status",
            "--status-json",
            "--status-timer=1",
            "--potfile-disable",
            "--logfile-disable",
            "--outfile",
            str(self._password_output_path),
            "--outfile-format=2",
        ]

        # Workload profile.
        cmd.extend(["-w", str(options.get("workload_profile", 2))])

        # Diccionario / wordlist.
        if dict_path := options.get("dictionary"):
            cmd.append(dict_path)

        # Reglas.
        if rules_path := options.get("rules"):
            cmd.extend(["-r", rules_path])

        # Máscara.
        if mask := options.get("mask"):
            cmd.append(mask)

        # Conjuntos personalizados.
        if cs1 := options.get("custom_charset_1"):
            cmd.extend(["-1", cs1])
        if cs2 := options.get("custom_charset_2"):
            cmd.extend(["-2", cs2])

        # PRINCE mode.
        if attack_mode == AttackMode.PRINCE:
            cmd.append("--prince")

        # Dispositivo OpenCL.
        if opencl_device := options.get("opencl_device"):
            cmd.extend(["--opencl-device", str(opencl_device)])

        # Self-test.
        if options.get("skip_self_test"):
            cmd.append("--self-test-disable")

        # Argumentos extra.
        cmd.extend(options.get("extra_args", []))

        return cmd

    # ------------------------------------------------------------------
    # Parseo de salida en vivo
    # ------------------------------------------------------------------

    async def parse_output(self, line: str) -> dict[str, Any] | None:
        """Procesa una línea de stdout/stderr de hashcat.

        Detecta y parsea:
          - Líneas ``--status-json`` (JSON) → progreso estructurado.
          - Líneas de log de hashcat → evento de log.
          - Líneas con ``hash:password`` → password crackeado.
        """
        stripped = line.strip()
        if not stripped:
            return None

        # Línea JSON de status (--status-json).
        if _JSON_STATUS_RE.match(stripped):
            return await self._parse_status_json(stripped)

        # Línea de log interno de hashcat.
        if any(stripped.startswith(p) for p in _HASHCAT_LOG_PREFIXES):
            return {"event": "hashcat_log", "line": stripped}

        # Posible línea de password crackeado (hash:password).
        if ":" in stripped and not stripped.startswith("{"):
            parts = stripped.split(":", 1)
            if len(parts) == 2 and len(parts[0]) > 10:  # parece hash
                self._cracked_password = parts[1].strip()
                return {
                    "event": "password_cracked",
                    "password": self._cracked_password,
                    "raw": stripped,
                }

        return None

    async def _parse_status_json(self, raw: str) -> dict[str, Any] | None:
        """Parse y acumula una línea de status JSON de hashcat."""
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return None

        status: str = str(data.get("status_string") or data.get("status", "Unknown"))
        progress = data.get("progress", {})

        # Fracción de progreso.
        if isinstance(progress, list) and len(progress) >= 2:
            processed = int(progress[0] or 0)
            total = int(progress[1] or 0)
            frac = processed / total if total > 0 else 0.0
        elif isinstance(progress, dict):
            guess_base = float(progress.get("guessBase", 0) or 1)
            guess_mod = float(progress.get("guessMod", 0) or 0)
            frac = guess_mod / guess_base if guess_base > 0 else 0.0
            processed = int(progress.get("curHashes", 0) or 0)
            total = int(progress.get("totalHashes", 0) or 0)
        else:
            processed = total = 0
            frac = 0.0

        # Velocidad en H/s.
        raw_speed = data.get("speed", 0)
        if isinstance(raw_speed, (int, float)):
            speed_hs = int(raw_speed)
        else:
            devices = data.get("devices", [])
            speed_hs = sum(
                int(device.get("speed", 0) or 0)
                for device in devices
                if isinstance(device, dict)
            )

        # Hashes recuperados.
        recovered_raw = data.get("recovered_hashes", data.get("recovered", 0))
        recovered = int(recovered_raw[0] or 0) if isinstance(recovered_raw, list) else int(recovered_raw)

        p = CrackingProgress(
            job_id=self._job_id,
            status=status,
            progress_denom=frac,
            speed=speed_hs,
            time_estimated=(progress.get("estimatedStop", 0) if isinstance(progress, dict) else None),
            hashes_processed=processed,
            hashes_total=total,
            recovered=recovered,
            rejected=data.get("rejected", 0),
            raw_json=data,
        )
        self._progress.append(p)
        if self._progress_callback is not None:
            self._progress_callback(p)

        return {
            "event": "status",
            "status": status,
            "progress": frac,
            "speed": speed_hs,
            "recovered": recovered,
        }

    # ------------------------------------------------------------------
    # Resultados finales
    # ------------------------------------------------------------------

    async def collect_results(self) -> dict[str, Any]:
        """Retorna resultados estructurados post-ejecución.

        Si hashcat recuperó al menos un hash, ejecuta ``--show`` para
        obtener la contraseña en texto plano.
        """
        raw = self._raw_result
        exit_code = raw.get("exit_code")
        cracked = False
        password = self._cracked_password

        # La salida de candidatos recuperados va a un archivo temporal 0600.
        # Se lee una vez y se elimina inmediatamente para no persistir secretos.
        if exit_code == 0 and not password:
            password = self._extract_password_file()

        self._password_output_path.unlink(missing_ok=True)

        cracked = password is not None

        return {
            "cracked": cracked,
            "password": password,
            "exit_code": exit_code,
            "peak_speed": max((p.speed for p in self._progress), default=0),
            "stages_executed": 1,
            "total_runtime_seconds": raw.get("runtime_seconds"),
            "log_path": raw.get("log_path"),
            "sha256": raw.get("sha256"),
        }

    def _extract_password_file(self) -> str | None:
        """Lee la primera contraseña recuperada sin incluirla en logs."""
        try:
            with self._password_output_path.open("r", encoding="utf-8", errors="replace") as stream:
                password = stream.readline().rstrip("\r\n")
                return password or None
        except OSError:
            return None

    async def cleanup(self) -> None:
        await super().cleanup()
        self._password_output_path.unlink(missing_ok=True)


# --- Registro automático al importar el módulo -----------------------------

from aegiswifi.adapters.registry import register_adapter  # noqa: E402

register_adapter("password_audit", HashcatAdapter)
