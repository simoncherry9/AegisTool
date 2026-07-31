"""Parser del archivo de alcance YAML → ScopeFile (minuta §12.2)."""

from __future__ import annotations

from pathlib import Path

import yaml

from aegiswifi.core.exceptions import ValidationFailed
from aegiswifi.scope.schemas import ScopeFile


def parse_scope_yaml(text: str) -> ScopeFile:
    """Parsea y valida un documento YAML de alcance."""
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ValidationFailed(f"YAML inválido: {exc}") from exc
    if not isinstance(raw, dict):
        raise ValidationFailed("el archivo de alcance debe ser un mapeo YAML")
    try:
        return ScopeFile.model_validate(raw)
    except Exception as exc:  # pydantic ValidationError
        raise ValidationFailed(f"alcance inválido: {exc}") from exc


def parse_scope_file(path: str | Path) -> ScopeFile:
    p = Path(path)
    if not p.exists():
        raise ValidationFailed(f"no existe el archivo de alcance: {p}")
    return parse_scope_yaml(p.read_text(encoding="utf-8"))
