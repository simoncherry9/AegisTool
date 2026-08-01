"""Módulo para ejecución de comandos con privilegios elevados (sudo / root) (minuta §34)."""

from __future__ import annotations

import asyncio
import os

from structlog import get_logger

from aegiswifi.core.config import get_settings
from aegiswifi.core.security import decrypt_secret

log = get_logger(__name__)


def get_sudo_cmd_prefix() -> list[str]:
    """Retorna el prefijo sudo si no se ejecuta como root.

    Si el proceso ya corre como root (euid == 0), retorna ``[]``.
    Si hay clave sudo guardada en ajustes, retorna ``["sudo", "-S", "-E"]``.
    De lo contrario, retorna ``["sudo", "-n", "-E"]`` por defecto en Kali.
    """
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        return []

    settings = get_settings()
    if settings.security.sudo_password:
        return ["sudo", "-S", "-E"]

    return ["sudo", "-n", "-E"]


def get_sudo_password_bytes() -> bytes | None:
    """Retorna los bytes de la clave sudo cifrada si está configurada."""
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        return None

    settings = get_settings()
    if settings.security.sudo_password:
        try:
            raw = decrypt_secret(settings.security.sudo_password)
            return f"{raw}\n".encode("utf-8")
        except Exception as exc:
            log.warning("error decrypting sudo_password", error=str(exc))

    return None


async def run_privileged_cmd(
    cmd: list[str],
    timeout: float | None = 15,
) -> tuple[str, str, int]:
    """Ejecuta un comando privilegiado (iw, ip, airmon-ng, airodump-ng, etc.).

    Returns:
        ``(stdout, stderr, exit_code)``.
    """
    prefix = get_sudo_cmd_prefix()
    full_cmd = prefix + cmd if prefix else cmd
    pass_bytes = get_sudo_password_bytes() if (prefix and "-S" in prefix) else None

    try:
        proc = await asyncio.create_subprocess_exec(
            *full_cmd,
            stdin=asyncio.subprocess.PIPE if pass_bytes else None,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            if timeout:
                stdout_b, stderr_b = await asyncio.wait_for(
                    proc.communicate(input=pass_bytes), timeout=timeout
                )
            else:
                stdout_b, stderr_b = await proc.communicate(input=pass_bytes)
        except TimeoutError:
            proc.kill()
            await proc.wait()
            return "", "timeout", -1

        return (
            stdout_b.decode("utf-8", errors="replace"),
            stderr_b.decode("utf-8", errors="replace"),
            proc.returncode or 0,
        )
    except FileNotFoundError:
        return "", f"{cmd[0]}: command not found", 127
    except OSError as exc:
        log.warning("privileged execution error", cmd=cmd[0], error=str(exc))
        return "", str(exc), -1


async def run_ip_privileged(args: list[str], timeout: int = 10) -> tuple[str, str]:
    """Ejecuta ``ip`` con privilegios elevados para modificaciones de red."""
    stdout, stderr, _ = await run_privileged_cmd(["ip"] + args, timeout=timeout)
    return stdout, stderr


async def run_iw_privileged(args: list[str], timeout: int = 15) -> tuple[str, str]:
    """Ejecuta ``iw`` con privilegios elevados para modificaciones de interfaz."""
    stdout, stderr, _ = await run_privileged_cmd(["iw"] + args, timeout=timeout)
    return stdout, stderr


async def run_airmon_privileged(args: list[str], timeout: int = 15) -> tuple[str, str]:
    """Ejecuta ``airmon-ng`` con privilegios elevados."""
    stdout, stderr, _ = await run_privileged_cmd(["airmon-ng"] + args, timeout=timeout)
    return stdout, stderr


async def run_aireplay_privileged(args: list[str], timeout: int = 15) -> tuple[str, str]:
    """Ejecuta ``aireplay-ng`` con privilegios elevados."""
    stdout, stderr, _ = await run_privileged_cmd(["aireplay-ng"] + args, timeout=timeout)
    return stdout, stderr


async def run_wash_privileged(args: list[str], timeout: int = 30) -> tuple[str, str]:
    """Ejecuta ``wash`` con privilegios elevados para detección WPS."""
    stdout, stderr, _ = await run_privileged_cmd(["wash"] + args, timeout=timeout)
    return stdout, stderr


async def run_reaver_privileged(args: list[str], timeout: int = 300) -> tuple[str, str]:
    """Ejecuta ``reaver`` con privilegios elevados para ataque WPS."""
    stdout, stderr, _ = await run_privileged_cmd(["reaver"] + args, timeout=timeout)
    return stdout, stderr


async def run_bully_privileged(args: list[str], timeout: int = 300) -> tuple[str, str]:
    """Ejecuta ``bully`` con privilegios elevados para ataque WPS."""
    stdout, stderr, _ = await run_privileged_cmd(["bully"] + args, timeout=timeout)
    return stdout, stderr


async def run_hcxdumptool_privileged(args: list[str], timeout: int = 120) -> tuple[str, str]:
    """Ejecuta ``hcxdumptool`` con privilegios elevados para captura PMKID."""
    stdout, stderr, _ = await run_privileged_cmd(["hcxdumptool"] + args, timeout=timeout)
    return stdout, stderr


async def spawn_privileged_process(
    cmd: list[str],
) -> asyncio.subprocess.Process | None:
    """Spawnea un subproceso privilegiado de larga duración (ej. airodump-ng, tcpdump)."""
    prefix = get_sudo_cmd_prefix()
    full_cmd = prefix + cmd if prefix else cmd
    pass_bytes = get_sudo_password_bytes() if (prefix and "-S" in prefix) else None

    try:
        proc = await asyncio.create_subprocess_exec(
            *full_cmd,
            stdin=asyncio.subprocess.PIPE if pass_bytes else None,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        if pass_bytes and proc.stdin:
            proc.stdin.write(pass_bytes)
            await proc.stdin.drain()
        return proc
    except FileNotFoundError:
        log.error("privileged tool binary not found", binary=cmd[0])
        return None
    except OSError as exc:
        log.error("failed to spawn privileged process", binary=cmd[0], error=str(exc))
        return None

