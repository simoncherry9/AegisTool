"""API REST para verificación de herramientas del sistema."""

from __future__ import annotations

import os

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from aegiswifi.api.v1.users import require_admin
from aegiswifi.core.config import get_settings
from aegiswifi.core.security import encrypt_secret, redact
from aegiswifi.database.models import User
from aegiswifi.tools.schemas import ToolsCheckResult
from aegiswifi.tools.service import check_tools

router = APIRouter(prefix="/tools", tags=["tools"])


class SudoConfigPayload(BaseModel):
    password: str


@router.get("/check", response_model=ToolsCheckResult)
async def tools_check() -> ToolsCheckResult:
    """Verifica qué herramientas del sistema están instaladas."""
    return check_tools()


@router.get("/sudo-status")
def get_sudo_status() -> dict[str, object]:
    """Retorna si la contraseña sudo está configurada."""
    settings = get_settings()
    configured = bool(settings.security.sudo_password)
    return {
        "configured": configured,
        "masked": redact("*" * 8) if configured else None,
    }


@router.post("/sudo-config")
def set_sudo_config(
    payload: SudoConfigPayload,
    _current_user: User = Depends(require_admin),
) -> dict[str, str]:
    """Guarda la contraseña de sudo cifrada para ser utilizada por los adaptadores privileged."""
    settings = get_settings()
    encrypted = encrypt_secret(payload.password)
    settings.security.sudo_password = encrypted

    # Persistir únicamente el token cifrado, nunca la contraseña original.
    env_file = settings.paths.data_dir.parent / ".env"
    lines = env_file.read_text(encoding="utf-8").splitlines() if env_file.exists() else []
    new_lines = [line for line in lines if not line.startswith("AEGISWIFI_SECURITY__SUDO_PASSWORD=")]
    new_lines.append(f"AEGISWIFI_SECURITY__SUDO_PASSWORD={encrypted}")
    temporary_file = env_file.with_suffix(".tmp")
    temporary_file.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    if os.name != "nt":
        temporary_file.chmod(0o600)
    temporary_file.replace(env_file)

    return {"status": "ok", "message": "Contraseña de sudo guardada de forma segura (cifrada)"}
