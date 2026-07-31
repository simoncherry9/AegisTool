#!/usr/bin/env bash
# AegisWiFi — instalación completa (minuta §35).
#   ./install.sh          instala y levanta todo
#   ./install.sh --build  compila frontend (producción) en vez de dev-server
#   ./install.sh --stop   detiene los procesos en background
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${PYTHON:-python3}"
VENV_DIR="${VENV:-$REPO/.venv}"
BUILD_MODE="${1:-dev}"  # dev | --build

log()  { printf '\033[1;34m[aegis]\033[0m %s\n' "$*"; }
ok()   { printf '\033[1;32m[  ok]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[warn]\033[0m %s\n' "$*" >&2; }
err()  { printf '\033[1;31m[error]\033[0m %s\n' "$*" >&2; }
require_cmd() { command -v "$1" >/dev/null 2>&1 || { err "missing dependency: $1"; exit 1; }; }

# ─── stop ────────────────────────────────────────────────────────────────────
if [[ "${1:-}" == "--stop" ]]; then
  log "deteniendo procesos AegisWiFi…"
  pkill -f "uvicorn aegiswifi.main:app" 2>/dev/null && ok "backend detenido" || warn "backend no estaba corriendo"
  pkill -f "vite" 2>/dev/null && ok "frontend detenido" || warn "frontend no estaba corriendo"
  exit 0
fi

# ─── 1. Requisitos ───────────────────────────────────────────────────────────
log "comprobando dependencias del sistema…"
require_cmd "$PYTHON_BIN"
require_cmd git
require_cmd npm

if [[ -f /etc/os-release ]] && grep -qi 'kali' /etc/os-release; then
  log "Kali Linux detectado."
  PACKAGES=(python3-venv python3-dev pkg-config libssl-dev)
  missing=()
  for pkg in "${PACKAGES[@]}"; do
    if ! dpkg -s "$pkg" &>/dev/null; then missing+=("$pkg"); fi
  done
  if [[ ${#missing[@]} -gt 0 ]]; then
    warn "instalando paquetes faltantes: ${missing[*]}"
    sudo apt-get update -qq && sudo apt-get install -y -qq "${missing[@]}"
  fi
else
  warn "no se detectó Kali Linux — las herramientas Wi-Fi pueden no funcionar"
fi

# ─── 2. Virtualenv ───────────────────────────────────────────────────────────
if [[ ! -d "$VENV_DIR" ]]; then
  log "creando virtualenv en $VENV_DIR…"
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

log "actualizando pip…"
pip install --upgrade pip --quiet

log "instalando backend (editable)…"
pip install -e "$REPO[dev]" --quiet

# ─── 3. .env con Fernet key autogenerada ─────────────────────────────────────
ENV_FILE="$REPO/.env"
if [[ ! -f "$ENV_FILE" ]]; then
  log "generando .env con clave Fernet…"
  FERNET_KEY=$(python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
  cat > "$ENV_FILE" <<ENVEOF
# AegisWiFi — generado automáticamente por install.sh
AEGISWIFI_ENVIRONMENT=development
AEGISWIFI_DEBUG=true
AEGISWIFI_LOG_LEVEL=DEBUG
AEGISWIFI_LOG_JSON=false
AEGISWIFI_API_HOST=127.0.0.1
AEGISWIFI_API_PORT=8001
AEGISWIFI_DATABASE__URL=
AEGISWIFI_PATHS__DATA_DIR=$REPO/data
AEGISWIFI_PATHS__EVIDENCE_DIR=$REPO/data/evidence
AEGISWIFI_SECURITY__REQUIRE_AUTH=true
AEGISWIFI_SECURITY__ENCRYPTION_KEY_B64=$FERNET_KEY
AEGISWIFI_JOBS__MAX_WORKERS=2
AEGISWIFI_JOBS__HEARTBEAT_INTERVAL=15
AEGISWIFI_JOBS__DEFAULT_TIMEOUT=300
AEGISWIFI_JOBS__EVENT_BUFFER_SIZE=1000
AEGISWIFI_JOBS__LOG_DIR=$REPO/data/job_logs
AEGISWIFI_JOBS__PROCESS_KILL_TIMEOUT=5
ENVEOF
  ok ".env creado con clave Fernet"
else
  log ".env ya existe, se conserva"
fi

# ─── 4. Directorios de datos ─────────────────────────────────────────────────
log "creando directorios de datos…"
mkdir -p "$REPO/data/evidence" "$REPO/data/job_logs" "$REPO/data/hashes"

# ─── 5. Frontend ─────────────────────────────────────────────────────────────
log "instalando dependencias del frontend…"
(cd "$REPO/frontend" && npm install --silent)

if [[ "${1:-}" == "--build" ]]; then
  log "compilando frontend (producción)…"
  (cd "$REPO/frontend" && npm run build)
  ok "frontend compilado en frontend/dist/"
else
  log "frontend listo para dev-server (npm run dev)"
fi

# ─── 6. Migraciones ──────────────────────────────────────────────────────────
log "aplicando migraciones de base de datos…"
if "$VENV_DIR/bin/alembic" -c "$REPO/backend/alembic.ini" upgrade head 2>/dev/null; then
  ok "migraciones aplicadas"
else
  warn "alembic falló — ejecuta: source .venv/bin/activate && alembic -c backend/alembic.ini upgrade head"
fi

# ─── 7. Diagnóstico ──────────────────────────────────────────────────────────
log "verificando instalación…"
python -c "import aegiswifi; print('  aegiswifi', aegiswifi.__version__)" 2>/dev/null \
  && ok "backend importable" \
  || err "no se pudo importar aegiswifi"

if "$VENV_DIR/bin/aegiswifi" --help >/dev/null 2>&1; then
  ok "CLI lista: aegiswifi --help"
fi

ok "instalación completada"

# ─── 8. Arrancar servicios ───────────────────────────────────────────────────
log "iniciando servicios…"

# Detener instancias previas si las hubiera
pkill -f "uvicorn aegiswifi.main:app" 2>/dev/null || true

# Backend (uvicorn)
log "  → backend  en  http://127.0.0.1:8001"
"$VENV_DIR/bin/uvicorn" aegiswifi.main:app \
  --host 127.0.0.1 --port 8001 \
  --reload \
  --log-level info > "$REPO/data/backend.log" 2>&1 &
BACKEND_PID=$!

# Frontend (vite dev server)
log "  → frontend en http://127.0.0.1:5173"
(cd "$REPO/frontend" && npm run dev) > "$REPO/data/frontend.log" 2>&1 &
FRONTEND_PID=$!

# Pequeña pausa para que arranquen
sleep 3

# Verificar que levantaron
if kill -0 "$BACKEND_PID" 2>/dev/null; then
  ok "backend corriendo (PID $BACKEND_PID)"
else
  err "backend no arrancó — revisa data/backend.log"
fi

if kill -0 "$FRONTEND_PID" 2>/dev/null; then
  ok "frontend corriendo (PID $FRONTEND_PID)"
else
  warn "frontend no arrancó — revisa data/frontend.log"
fi

echo ""
echo "  ┌────────────────────────────────────────────────────────┐"
echo "  │  AegisWiFi está corriendo                              │"
echo "  │                                                        │"
echo "  │  Frontend :  http://127.0.0.1:5173                     │"
echo "  │  Backend  :  http://127.0.0.1:8001                     │"
echo "  │  API docs :  http://127.0.0.1:8001/docs                │"
echo "  │                                                        │"
echo "  │  Para detener:  ./install.sh --stop                    │"
echo "  │  Para reiniciar: ./install.sh                          │"
echo "  └────────────────────────────────────────────────────────┘"
echo ""
