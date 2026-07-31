"""Servicio de detección de herramientas del sistema."""

from __future__ import annotations

import platform
import shutil
import subprocess

from aegiswifi.tools.schemas import ToolInfo, ToolsCheckResult

# Herramientas requeridas para auditoría Wi-Fi
TOOLS_DEFINITIONS: list[dict] = [
    # === Captura e inyección ===
    {
        "name": "airodump-ng",
        "binary": "airodump-ng",
        "description": "Captura de paquetes 802.11",
        "category": "capture",
    },
    {
        "name": "aireplay-ng",
        "binary": "aireplay-ng",
        "description": "Inyección de paquetes",
        "category": "capture",
    },
    {
        "name": "airmon-ng",
        "binary": "airmon-ng",
        "description": "Gestión de modo monitor",
        "category": "capture",
    },
    {
        "name": "aircrack-ng",
        "binary": "aircrack-ng",
        "description": "Cracking WEP/WPA",
        "category": "cracking",
    },
    # === Conversión de hashes ===
    {
        "name": "hcxpcapngtool",
        "binary": "hcxpcapngtool",
        "description": "Conversión de capturas a hashes 22000",
        "category": "capture",
    },
    # === Cracking ===
    {
        "name": "hashcat",
        "binary": "hashcat",
        "description": "Cracking de hashes GPU/CPU",
        "category": "cracking",
    },
    # === Interfaces ===
    {
        "name": "iwconfig",
        "binary": "iwconfig",
        "description": "Configuración de interfaces inalámbricas (wireless-tools)",
        "category": "interface",
    },
    {
        "name": "iw",
        "binary": "iw",
        "description": "Configuración nl80211",
        "category": "interface",
    },
    {
        "name": "ifconfig",
        "binary": "ifconfig",
        "description": "Configuración de interfaces de red",
        "category": "interface",
    },
    # === Análisis ===
    {
        "name": "tshark",
        "binary": "tshark",
        "description": "Análisis de paquetes CLI (Wireshark)",
        "category": "analysis",
    },
    {
        "name": "tcpdump",
        "binary": "tcpdump",
        "description": "Captura de paquetes CLI",
        "category": "analysis",
    },
    {
        "name": "nmap",
        "binary": "nmap",
        "description": "Escaneo de redes",
        "category": "analysis",
    },
    # === Utilidades ===
    {
        "name": "xterm",
        "binary": "xterm",
        "description": "Terminal para procesos externos",
        "category": "utility",
    },
    {
        "name": "Python",
        "binary": "python3",
        "description": "Entorno de ejecución",
        "category": "utility",
    },
    {
        "name": "Node.js",
        "binary": "node",
        "description": "Entorno frontend",
        "category": "utility",
    },
]


def _get_version(binary: str) -> str | None:
    """Intenta obtener la versión de una herramienta."""
    try:
        result = subprocess.run(
            [binary, "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        # Tomar solo la primera línea
        line = (result.stdout or result.stderr or "").strip().split("\n")[0]
        return line[:120] if line else None
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None


def check_tools() -> ToolsCheckResult:
    """Ejecuta la verificación de todas las herramientas definidas."""
    system = platform.system().lower()

    tools: list[ToolInfo] = []
    installed_count = 0

    for tool_def in TOOLS_DEFINITIONS:
        binary = tool_def["binary"]

        # En Windows, los binarios pueden tener extensión .exe
        if system == "windows":
            if shutil.which(binary) is None:
                binary = f"{binary}.exe"

        found = shutil.which(binary) is not None
        version = _get_version(binary) if found else None

        if found:
            installed_count += 1

        tools.append(
            ToolInfo(
                name=tool_def["name"],
                binary=tool_def["binary"],
                installed=found,
                version=version,
                description=tool_def["description"],
                category=tool_def["category"],
            )
        )

    return ToolsCheckResult(
        tools=tools,
        total=len(tools),
        installed=installed_count,
        missing=len(tools) - installed_count,
        os=system,
    )
