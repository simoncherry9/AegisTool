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
