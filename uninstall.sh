#!/usr/bin/env bash
# AegisWiFi uninstaller — minuta §35.
#   ./uninstall.sh          conserva datos y config
#   ./uninstall.sh --purge  borra data, .env, node_modules
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PURGE=0
[[ "${1:-}" == "--purge" ]] && PURGE=1

log() { printf '\033[1;34m[aegis]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[warn]\033[0m %s\n' "$*" >&2; }

# 1. Detener procesos en background (uvicorn / vite)
log "deteniendo procesos activos…"
pkill -f "uvicorn aegiswifi.main:app" 2>/dev/null && log "  backend detenido" || true
pkill -f "vite" 2>/dev/null && log "  frontend detenido" || true

# 2. Restaurar interfaces (best-effort)
if command -v aegiswifi >/dev/null 2>&1; then
  log "restaurando interfaces (best-effort)"
  aegiswifi interface restore-all 2>/dev/null || warn "no se pudieron restaurar interfaces"
fi

# 3. Eliminar virtualenv y artefactos build
log "eliminando virtualenv y artefactos…"
rm -rf "$REPO/.venv" "$REPO/build" "$REPO/dist" "$REPO"/*.egg-info

# 4. Eliminar node_modules del frontend
if [[ -d "$REPO/frontend/node_modules" ]]; then
  log "eliminando node_modules…"
  rm -rf "$REPO/frontend/node_modules" "$REPO/frontend/dist"
fi

# 5. Systemd (solo Linux)
if [[ -f /etc/systemd/system/aegiswifi.service ]]; then
  log "eliminando unit de systemd…"
  sudo systemctl stop aegiswifi 2>/dev/null || true
  sudo rm -f /etc/systemd/system/aegiswifi.service
  sudo systemctl daemon-reload 2>/dev/null || true
fi

# 6. Datos: mantener por defecto, borrar con --purge
if [[ "$PURGE" -eq 1 ]]; then
  log "--purge: eliminando data/, .env, config.yaml y bases de datos…"
  rm -rf "$REPO/data" "$REPO/.env" "$REPO/config.yaml" "$REPO"/*.db
  find "$REPO" -name "__pycache__" -prune -exec rm -rf {} + 2>/dev/null || true
  find "$REPO" -name "*.pyc" -delete 2>/dev/null || true
else
  log "conservando data/, .env, node_modules (usa --purge para borrarlos)"
fi

log "desinstalación completa."
