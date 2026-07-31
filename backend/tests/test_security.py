"""Tests de redacción y cifrado de secretos (minuta §19)."""

from __future__ import annotations

from aegiswifi.core.security import decrypt_secret, encrypt_secret, redact


def test_redact_typical_password():
    assert redact("Empresa2024!") == "Empr*******!"


def test_redact_short():
    assert redact("abc") == "***"
    assert redact("ab") == "**"
    assert redact("") == ""
    assert redact(None) == ""


def test_encrypt_decrypt_roundtrip():
    token = encrypt_secret("SuperSecret2024!")
    assert "SuperSecret" not in token
    assert decrypt_secret(token) == "SuperSecret2024!"
