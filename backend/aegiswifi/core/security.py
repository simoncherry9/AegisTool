"""Protección de credenciales recuperadas y secretos (minuta §19).

* Cifrado en reposo con Fernet (cryptography).
* Redacción para logs/informes/notificaciones.
* Persistencia best-effort de la clave en ``paths.data_dir/.aegis_key``.
"""

from __future__ import annotations

import contextlib
from pathlib import Path

from cryptography.fernet import Fernet

from aegiswifi.core.config import get_settings

_KEY_FILE_NAME = ".aegis_key"


def _key_path() -> Path:
    return get_settings().paths.data_dir / _KEY_FILE_NAME


def get_encryption_key() -> str:
    """Devuelve una clave Fernet en base64, generándola/persistiéndola si falta."""
    settings = get_settings()
    configured = settings.security.encryption_key_b64
    if configured:
        return configured
    key_file = _key_path()
    if key_file.exists():
        return key_file.read_text(encoding="utf-8").strip()
    key = Fernet.generate_key().decode("utf-8")
    key_file.parent.mkdir(parents=True, exist_ok=True)
    key_file.write_text(key, encoding="utf-8")
    # Windows no soporta chmod Unix; la ACL del directorio queda como respaldo.
    with contextlib.suppress(OSError):
        key_file.chmod(0o600)
    return key


def _fernet() -> Fernet:
    return Fernet(get_encryption_key().encode("utf-8"))


def encrypt_secret(plaintext: str) -> str:
    """Cifra un secreto (p. ej. una contraseña WPA2 recuperada) para almacenarlo."""
    return _fernet().encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_secret(token: str) -> str:
    """Descifra un secreto previamente cifrado con :func:`encrypt_secret`."""
    return _fernet().decrypt(token.encode("utf-8")).decode("utf-8")


def redact(value: str | None, visible: int = 4) -> str:
    """Representación redactada, p. ej. ``Empr*********!`` (minuta §19)."""
    if not value:
        return ""
    if len(value) <= visible:
        return "*" * len(value)
    # Mantener visible el prefijo y el último carácter si NO es alfanumérico.
    keep_tail = len(value) > visible + 1 and not value[-1].isalnum()
    head = value[:visible]
    tail = value[-1] if keep_tail else ""
    middle = "*" * (len(value) - visible - len(tail))
    return f"{head}{middle}{tail}"


# --- Autenticación & JWT -----------------------------------------------------

import base64
import hashlib
import hmac
import json
import time
from typing import cast


def hash_password(password: str) -> str:
    """Hash seguro de contraseña usando PBKDF2-HMAC-SHA256 con salt."""
    salt = get_encryption_key().encode("utf-8")[:16]
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000)
    return key.hex()


def verify_password(password: str, password_hash: str) -> bool:
    """Verifica si la contraseña coincide con el hash."""
    return hmac.compare_digest(hash_password(password), password_hash)


def _urlsafe_b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _urlsafe_b64decode(data: str) -> bytes:
    padding = "=" * (4 - (len(data) % 4))
    return base64.urlsafe_b64decode(data + padding)


def create_access_token(
    user_id: int, username: str, role: str, expires_in_seconds: int = 86400
) -> str:
    """Genera un JWT firmado con HMAC-SHA256 usando la clave Fernet como secreto."""
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": str(user_id),
        "username": username,
        "role": role,
        "exp": int(time.time()) + expires_in_seconds,
    }

    header_b64 = _urlsafe_b64encode(json.dumps(header).encode("utf-8"))
    payload_b64 = _urlsafe_b64encode(json.dumps(payload).encode("utf-8"))

    signing_input = f"{header_b64}.{payload_b64}".encode()
    secret = get_encryption_key().encode("utf-8")
    signature = hmac.new(secret, signing_input, hashlib.sha256).digest()
    sig_b64 = _urlsafe_b64encode(signature)

    return f"{header_b64}.{payload_b64}.{sig_b64}"


def decode_access_token(token: str) -> dict[str, object] | None:
    """Valida y decodifica un JWT. Devuelve el payload si es válido o None."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        header_b64, payload_b64, sig_b64 = parts

        signing_input = f"{header_b64}.{payload_b64}".encode()
        secret = get_encryption_key().encode("utf-8")
        expected_sig = hmac.new(secret, signing_input, hashlib.sha256).digest()

        if not hmac.compare_digest(_urlsafe_b64encode(expected_sig), sig_b64):
            return None

        payload_bytes = _urlsafe_b64decode(payload_b64)
        payload = cast(dict[str, object], json.loads(payload_bytes.decode("utf-8")))

        expires_at = payload.get("exp", 0)
        if not isinstance(expires_at, (int, float)) or expires_at < time.time():
            return None

        return payload
    except Exception:
        return None
