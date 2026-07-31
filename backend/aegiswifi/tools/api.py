"""API REST para verificación de herramientas del sistema."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from pydantic import BaseModel
from aegiswifi.core.config import get_settings
from aegiswifi.core.security import encrypt_secret, redact
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
def set_sudo_config(payload: SudoConfigPayload) -> dict[str, str]:
    """Guarda la contraseña de sudo cifrada para ser utilizada por los adaptadores privileged."""
    settings = get_settings()
    encrypted = encrypt_secret(payload.password)
    settings.security.sudo_password = encrypted

    # Actualizar o persistir en .env de forma segura
    env_file = settings.paths.data_dir.parent / ".env"
    if env_file.exists():
        lines = env_file.read_text(encoding="utf-8").splitlines()
        new_lines = [l for l in lines if not l.startswith("AEGISWIFI_SECURITY__SUDO_PASSWORD=")]
        new_lines.append(f"AEGISWIFI_SECURITY__SUDO_PASSWORD={encrypted}")
        env_file.write_text("\n".join(new_lines) + "\n", encoding="utf-8")

    return {"status": "ok", "message": "Contraseña de sudo guardada de forma segura (cifrada)"}
