"""Clasificación RSN de redes inalámbricas (minuta §14, §37).

Traduce columnas del CSV de airodump-ng (Privacy, Cipher,
Authentication, WPS, flags) a clasificaciones estructuradas:
protocolo de seguridad, AKM suites, PMF, modo de transición WPA3.

Toda la lógica es pura — sin IO, sin estado.
"""

from __future__ import annotations

from typing import Final

from aegiswifi.discovery.schemas import (
    PnfMode,
    SecurityProtocol,
    TransitionMode,
)

# ── Mapas de traducción ─────────────────────────────────────────────


_PRIVACY_MAP: Final[dict[str, SecurityProtocol]] = {
    "OPN": SecurityProtocol.OPEN,
    "WEP": SecurityProtocol.WEP,
    "WPA": SecurityProtocol.WPA,
    "WPA2": SecurityProtocol.WPA2,
    "WPA3": SecurityProtocol.WPA3,
    "WPA2WPA3": SecurityProtocol.WPA2_WPA3,
    "WPA1WPA2": SecurityProtocol.WPA_WPA2,
    "WPA1+WPA2": SecurityProtocol.WPA_WPA2,
    "WPA2+WPA3": SecurityProtocol.WPA2_WPA3,
}

_AUTH_MAP: Final[dict[str, list[str]]] = {
    "": [],
    "PSK": ["PSK"],
    "SAE": ["SAE"],
    "PSK/SAE": ["PSK", "SAE"],
    "SAE/PSK": ["SAE", "PSK"],
    "MGT": ["EAP"],
    "FT PSK": ["FT-PSK"],
    "FT SAE": ["FT-SAE"],
    "FT EAP": ["FT-EAP"],
    "OWE": ["OWE"],
    "WPS": ["WPS"],
}

_CIPHER_MAP: Final[dict[str, str]] = {
    "": "UNKNOWN",
    "CCMP": "CCMP",
    "GCMP": "GCMP",
    "TKIP": "TKIP",
    "WEP-40": "WEP-40",
    "WEP-104": "WEP-104",
    "CCMP/TKIP": "CCMP",
    "TKIP/CCMP": "CCMP",
    "GCMP/CCMP": "GCMP",
    "CCMP/GCMP": "GCMP",
}

_PMF_KEYWORDS: Final[dict[str, PnfMode]] = {
    "MFP-REQ": PnfMode.REQUIRED,
    "PMF-REQ": PnfMode.REQUIRED,
    "MFP": PnfMode.OPTIONAL,
    "MFP-OPT": PnfMode.OPTIONAL,
    "PMF": PnfMode.OPTIONAL,
}

_WPS_KEYWORDS: Final[list[str]] = ["WPS", "WPA2WPS", "WPA3WPS"]

_WPA3_AKM: Final[list[str]] = ["SAE", "FT-SAE", "FT-EAP", "EAP"]
_WPA3_TRANSITION_KEYWORDS: Final[list[str]] = [
    "WPA3-Transition",
    "Transition",
    "WPA3TRANS",
    "MIXED",
    "WPA2/WPA3",
]
_DEGRADED_PROTOCOLS: Final[set[str]] = {"WPA", "WEP", "OPEN"}


# ── Clasificación principal ─────────────────────────────────────────


def classify_security(
    privacy: str = "",
    cipher: str = "",
    authentication: str = "",
    wps_col: str = "",
    flags: str = "",
    essid: str = "",
) -> dict:
    """Clasifica la seguridad de un AP desde columnas del CSV de airodump.

    Args:
        privacy:  Columna ``Privacy`` (OPN, WPA2, WPA3, WPA2WPA3, …).
        cipher:   Columna ``Cipher`` (CCMP, TKIP, GCMP, …).
        authentication: Columna ``Authentication`` (PSK, SAE, PSK/SAE, …).
        wps_col:  Columna ``WPS`` (si existe en el CSV; 0/1 o WPS).
        flags:    Columna ``Flags`` (MFP, MFP-REQ, WPS, …).
        essid:    ESSID usado para heurísticas adicionales.

    Returns:
        Diccionario con claves:
        - ``protocol`` (:class:`SecurityProtocol`)
        - ``akm`` (:class:`list`\[:class:`str`\])
        - ``cipher`` (:class:`str`)
        - ``pmf`` (:class:`PnfMode`)
        - ``wps`` (:class:`bool`)
        - ``wpa3_supported`` (:class:`bool`)
        - ``transition_mode`` (:class:`TransitionMode`)
        - ``degraded`` (:class:`bool`)
    """
    # 1. Protocolo base
    protocol = _resolve_protocol(privacy)
    flags_lower = flags.strip().upper()

    # 2. AKM
    akm_list = _resolve_akm(authentication, privacy, flags_lower)

    # 3. Cipher
    resolved_cipher = _resolve_cipher(cipher, flags_lower)

    # 4. PMF
    pmf = _resolve_pmf(flags_lower, privacy)

    # 5. WPS
    wps_enabled = _resolve_wps(wps_col, flags_lower, protocol)

    # 6. WPA3 support
    wpa3_supported = _resolve_wpa3_support(protocol, akm_list, flags_lower)

    # 7. Transition mode
    transition_mode = _resolve_transition_mode(privacy, flags_lower, wpa3_supported)

    return {
        "protocol": protocol,
        "akm": akm_list,
        "cipher": resolved_cipher,
        "pmf": pmf,
        "wps": wps_enabled,
        "wpa3_supported": wpa3_supported,
        "transition_mode": transition_mode,
        "degraded": protocol in _DEGRADED_PROTOCOLS,
    }


def _resolve_protocol(privacy: str) -> SecurityProtocol:
    """Resuelve el protocolo base desde la columna Privacy."""
    cleaned = privacy.strip()
    if not cleaned:
        return SecurityProtocol.UNKNOWN

    if cleaned in ("WPA2+WPA3", "WPA3+WPA2", "WPA2WPA3"):
        return SecurityProtocol.WPA2_WPA3
    if cleaned in ("WPA1+WPA2", "WPA1WPA2"):
        return SecurityProtocol.WPA_WPA2

    return _PRIVACY_MAP.get(cleaned, SecurityProtocol.UNKNOWN)


def _resolve_akm(
    authentication: str,
    privacy: str,
    flags: str,
) -> list[str]:
    """Resuelve las suites AKM desde Authentication + heurísticas."""
    auth = authentication.strip()
    if auth in _AUTH_MAP:
        return _AUTH_MAP[auth]

    # Heurística: inferir desde Privacy / flags
    priv = privacy.strip().upper()
    if priv in ("WPA3", "WPA2WPA3", "WPA3WPA2"):
        if "PSK" in flags and "SAE" in flags:
            return ["PSK", "SAE"]
        if "SAE" not in flags and "FT" in flags:
            return ["FT-PSK"]
        return ["SAE"]
    if priv in ("WPA2", "WPA1WPA2") or "PSK" in flags:
        return ["PSK"]

    return []


def _resolve_cipher(cipher: str, flags: str) -> str:
    """Resuelve el cipher suite."""
    c = cipher.strip()
    if c and c in _CIPHER_MAP:
        return _CIPHER_MAP[c]
    if "CCMP" in flags:
        return "CCMP"
    if "TKIP" in flags:
        return "TKIP"
    if "GCMP" in flags:
        return "GCMP"
    if c:
        return c.upper()
    return "UNKNOWN"


def _resolve_pmf(flags: str, privacy: str) -> PnfMode:
    """Resuelve el modo PMF desde flags."""
    for keyword, mode in _PMF_KEYWORDS.items():
        if keyword in flags:
            return mode
    # Heurística: WPA3 sin flags PMF → asumir optional
    priv = privacy.strip().upper()
    if priv in ("WPA3", "WPA2WPA3", "WPA3WPA2"):
        return PnfMode.OPTIONAL
    return PnfMode.UNKNOWN


def _resolve_wps(wps_col: str, flags: str, protocol: SecurityProtocol) -> bool:
    """Determina si WPS está habilitado."""
    wps = wps_col.strip()
    if wps == "1" or "WPS" in wps.upper():
        return True
    for kw in _WPS_KEYWORDS:
        if kw in flags:
            return True
    return False


def _resolve_wpa3_support(
    protocol: SecurityProtocol,
    akm_list: list[str],
    flags: str,
) -> bool:
    """Determina si el AP soporta WPA3."""
    if protocol in (SecurityProtocol.WPA3, SecurityProtocol.WPA2_WPA3):
        return True
    if any(akm in _WPA3_AKM for akm in akm_list):
        return True
    if "WPA3" in flags:
        return True
    return False


def _resolve_transition_mode(
    privacy: str,
    flags: str,
    wpa3_supported: bool,
) -> TransitionMode:
    """Resuelve el modo de transición WPA3."""
    priv = privacy.strip().upper()

    if priv == "WPA2WPA3":
        for kw in _WPA3_TRANSITION_KEYWORDS:
            if kw.upper() in flags:
                return TransitionMode.WPA3_TRANSITION
        return TransitionMode.WPA2_WPA3_MIXED

    if priv == "WPA3":
        return TransitionMode.NONE

    for kw in _WPA3_TRANSITION_KEYWORDS:
        if kw.upper() in flags:
            return TransitionMode.WPA3_TRANSITION

    if wpa3_supported and priv in ("WPA2",):
        return TransitionMode.WPA2_WPA3_MIXED

    return TransitionMode.NONE


# ── Degradación ────────────────────────────────────────────────────


def detect_degraded_security(
    current_protocol: SecurityProtocol,
    previous_protocol: SecurityProtocol,
) -> bool:
    """Detecta si la seguridad ha degradado entre dos observaciones.

    Una red que antes era WPA3 y ahora es WPA2, o que de tener
    autenticación pasó a estar abierta, se considera degradada.

    Args:
        current_protocol:  Protocolo actual.
        previous_protocol: Protocolo observado previamente.

    Returns:
        ``True`` si la seguridad ha empeorado.
    """
    rank = {
        SecurityProtocol.WPA3: 5,
        SecurityProtocol.WPA2_WPA3: 4,
        SecurityProtocol.WPA_WPA2: 3,
        SecurityProtocol.WPA2: 3,
        SecurityProtocol.WPA: 2,
        SecurityProtocol.WEP: 1,
        SecurityProtocol.OPEN: 0,
        SecurityProtocol.UNKNOWN: 0,
    }

    prev_rank = rank.get(previous_protocol, 0)
    curr_rank = rank.get(current_protocol, 0)
    return curr_rank < prev_rank