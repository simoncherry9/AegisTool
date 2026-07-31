"""Parser de CSV generado por airodump-ng (minuta §14, §37).

El CSV de airodump tiene dos secciones separadas por una línea en blanco:
  1. APs — cabecera ``BSSID, First time seen, ...``
  2. Clientes (stations) — cabecera ``Station MAC, First time seen, ...``

Toda la lógica es pura — sin IO, sin estado.
"""

from __future__ import annotations

import csv
import re
from typing import Any

_AP_FIELDS: list[str] = [
    "bssid",
    "first_seen",
    "last_seen",
    "channel",
    "speed",
    "privacy",
    "cipher",
    "authentication",
    "power",
    "beacons",
    "iv",
    "lan_ip",
    "id_length",
    "essid",
    "key",
]

_CLIENT_FIELDS: list[str] = [
    "station_mac",
    "first_seen",
    "last_seen",
    "power",
    "packets",
    "bssid",
    "probed_essids",
]


def parse_full_csv(content: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Parse el contenido completo de un CSV de airodump-ng.

    airodump-ng escribe dos bloques separados por una línea en blanco:
    primero la sección de APs (cabecera ``BSSID, ...``), luego la de
    clientes (cabecera ``Station MAC, ...``).

    Robusto a formatos parciales: si solo hay una sección (sin separador
    ``\\n\\n``), se clasifica por su cabecera.

    Args:
        content: Contenido completo del archivo CSV.

    Returns:
        ``(aps, clients)`` donde cada elemento es un ``dict`` con
        las columnas normalizadas. Ambos pueden estar vacíos si no
        hay datos o el CSV está malformado.
    """
    stripped = content.strip()
    if not stripped:
        return [], []

    parts = re.split(r"\n\s*\n", stripped)

    aps: list[dict[str, Any]] = []
    clients: list[dict[str, Any]] = []

    for part in parts:
        part = part.strip()
        if not part:
            continue
        # Clasificar la sección por su cabecera normalizada
        first_line = _norm(part.splitlines()[0])
        if first_line.startswith(_norm(_CLIENT_FIELDS[0])):
            clients.extend(_parse_section(part, _CLIENT_FIELDS))
        else:
            aps.extend(_parse_section(part, _AP_FIELDS))

    return aps, clients


def parse_ap_section(content: str) -> list[dict[str, Any]]:
    """Parse solo la sección de APs del CSV."""
    return _parse_section(content.strip(), _AP_FIELDS)


def parse_client_section(content: str) -> list[dict[str, Any]]:
    """Parse solo la sección de clientes del CSV."""
    return _parse_section(content.strip(), _CLIENT_FIELDS)


# ── Internal ───────────────────────────────────────────────────────


def _parse_section(content: str, fields: list[str]) -> list[dict[str, Any]]:
    """Parse una sección del CSV usando la cabecera esperada.

    La cabecera real de airodump-ng va en mayúsculas (``BSSID``); la
    normalizamos a minúsculas (``bssid``) vía ``fieldnames``. La fila de
    cabecera saltada de forma insensible a mayúsculas.
    """
    if not content:
        return []

    # airodump-ng puede incluir líneas de metadata (BSSID, ...)
    # Buscamos la línea que coincide con la cabecera esperada
    lines = content.splitlines()
    header_idx = _find_header(lines, fields)

    if header_idx is None:
        return []

    reader = csv.DictReader(
        lines[header_idx:],
        fieldnames=fields,
        restkey="extra",
        restval="",
    )

    first_field_norm = _norm(fields[0])
    results: list[dict[str, Any]] = []
    for row in reader:
        # Saltar la cabecera misma (normalizada: espacios→_, insensible a mayúsculas)
        if _norm(row.get(fields[0], "")) == first_field_norm:
            continue

        cleaned: dict[str, Any] = {k: v.strip() for k, v in row.items()}

        # Normalizar potencia a int | None
        if "power" in cleaned:
            cleaned["power"] = _parse_power(cleaned["power"])

        # Solo incluir filas con algún contenido (ignorar extras)
        meaningful = {k: v for k, v in cleaned.items() if k != "extra"}
        if any(v != "" and v is not None for v in meaningful.values()):
            results.append(cleaned)

    return results


def _norm(text: str) -> str:
    """Normaliza un token para comparación de cabeceras.

    airodump-ng escribe ``Station MAC`` / ``Probed ESSIDs`` (con espacios),
    mientras normalizamos a ``station_mac`` / ``probed_essids`` (guiones bajos).
    """
    return text.strip().lower().replace(" ", "_")


def _find_header(lines: list[str], fields: list[str]) -> int | None:
    """Encuentra el índice de la línea que contiene la cabecera esperada.

    La comparación normaliza espacios a ``_`` y es insensible a mayúsculas.
    """
    first_field = _norm(fields[0])
    for i, line in enumerate(lines):
        if _norm(line).startswith(first_field):
            return i
    return None


def _parse_power(power: str) -> int | None:
    """Convierte string de potencia (dBm) a entero.

    Maneja formatos como ``-45``, ``-45 dBm``, ``-45dBm``.
    """
    p = power.strip()
    if not p or p in ("?", "-1", "N/A"):
        return None
    p = p.replace(" dBm", "").replace("dBm", "").strip()
    try:
        return int(p)
    except ValueError:
        return None