#!/usr/bin/env bash
# AegisWiFi — instalación completa (minuta §35).
#   ./install.sh          instala y levanta todo
#   ./install.sh --build  compila frontend (producción) en vez de dev-server
#   ./install.sh --stop   detiene los procesos en background
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Seleccionar binario de Python (preferir python3.13 si existe)
if command -v python3.13 >/dev/null 2>&1; then
  PYTHON_BIN="python3.13"
else
  PYTHON_BIN="${PYTHON:-python3}"
fi

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

# ─── 0. Copiar config.example.yaml → config.yaml ─────────────────────────────
if [[ ! -f "$REPO/config.yaml" && -f "$REPO/config.example.yaml" ]]; then
  log "copiando config.example.yaml → config.yaml…"
  cp "$REPO/config.example.yaml" "$REPO/config.yaml"
  ok "config.yaml preparado"
fi

# ─── 1. Requisitos ───────────────────────────────────────────────────────────
log "comprobando dependencias del sistema con $PYTHON_BIN…"
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
  warn "no se detectó Kali Linux — las herramientas Wi-Fi pueden requerir paquetes adicionales"
fi

# ─── 2. Virtualenv ───────────────────────────────────────────────────────────
if [[ ! -d "$VENV_DIR" ]]; then
  log "creando entorno virtual en $VENV_DIR ($PYTHON_BIN)…"
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

PY_VENV="$VENV_DIR/bin/python"
PIP_VENV="$VENV_DIR/bin/pip"
ALEMBIC_VENV="$VENV_DIR/bin/alembic"

log "actualizando pip…"
"$PIP_VENV" install --upgrade pip --quiet

log "instalando backend en modo editable con dependencias dev (pip install -e '.[dev]')..."
(cd "$REPO" && "$PIP_VENV" install -e ".[dev]" --quiet)
ok "backend instalado"

# ─── 3. .env con Fernet key autogenerada ─────────────────────────────────────
ENV_FILE="$REPO/.env"
if [[ ! -f "$ENV_FILE" ]]; then
  log "generando .env con clave de cifrado Fernet…"
  FERNET_KEY=$("$PY_VENV" -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
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

# ─── 5. Migraciones (alembic upgrade head / make migrate) ────────────────────
log "aplicando migraciones de base de datos (make migrate)…"
if (cd "$REPO" && "$PY_VENV" -m alembic -c backend/alembic.ini upgrade head); then
  ok "migraciones aplicadas (esquema SQLite actualizado)"
else
  err "fallaron las migraciones de Alembic"
  exit 1
fi

# ─── 6. Diagnóstico de CLI y módulo ──────────────────────────────────────────
log "verificando instalación de aegiswifi…"
"$PY_VENV" -c "import aegiswifi; print('  aegiswifi versión:', aegiswifi.__version__)" 2>/dev/null \
  && ok "backend importable correctamente" \
  || err "no se pudo importar aegiswifi"

if "$VENV_DIR/bin/aegiswifi" --help >/dev/null 2>&1; then
  ok "CLI lista (aegiswifi --help)"
fi

# ─── 7. Frontend ─────────────────────────────────────────────────────────────
log "instalando dependencias del frontend (cd frontend && npm install)…"
(cd "$REPO/frontend" && npm install --silent)
ok "dependencias del frontend instaladas"

if [[ "${BUILD_MODE}" == "--build" ]]; then
  log "compilando frontend para producción…"
  (cd "$REPO/frontend" && npm run build)
  ok "frontend compilado en frontend/dist/"
else
  log "frontend preparado para dev-server (npm run dev)"
fi

ok "instalación y configuración completadas"

# ─── 8. Arrancar servicios ───────────────────────────────────────────────────
log "iniciando servicios de AegisWiFi…"

# Detener instancias previas si las hubiera
pkill -f "uvicorn aegiswifi.main:app" 2>/dev/null || true
pkill -f "vite" 2>/dev/null || true

# Backend (uvicorn / aegiswifi serve)
log "  → Levantando API Backend en http://127.0.0.1:8001"
"$VENV_DIR/bin/uvicorn" aegiswifi.main:app \
  --host 127.0.0.1 --port 8001 \
  --reload \
  --log-level info > "$REPO/data/backend.log" 2>&1 &
BACKEND_PID=$!

# Frontend (vite dev server)
log "  → Levantando Frontend Web en http://127.0.0.1:5173"
(cd "$REPO/frontend" && npm run dev) > "$REPO/data/frontend.log" 2>&1 &
FRONTEND_PID=$!

# Pausa para inicio
sleep 3

# Verificar estado de los procesos
if kill -0 "$BACKEND_PID" 2>/dev/null; then
  ok "Backend API corriendo (PID $BACKEND_PID)"
else
  err "Backend API no pudo arrancar — revisa data/backend.log"
fi

if kill -0 "$FRONTEND_PID" 2>/dev/null; then
  ok "Frontend Web corriendo (PID $FRONTEND_PID)"
else
  warn "Frontend no pudo arrancar — revisa data/frontend.log"
fi

echo ""
echo "  ┌────────────────────────────────────────────────────────┐"
echo "  │  AegisWiFi está corriendo exitosamente                 │"
echo "  │                                                        │"
echo "  │  Frontend Web :  http://127.0.0.1:5173                 │"
echo "  │  Backend API  :  http://127.0.0.1:8001                 │"
echo "  │  Documentación:  http://127.0.0.1:8001/docs            │"
echo "  │  Usuario Admin:  admin / admin123                      │"
echo "  │                                                        │"
echo "  │  Para detener:   ./install.sh --stop                   │"
echo "  │  Para reiniciar: ./install.sh                          │"
echo "  └────────────────────────────────────────────────────────┘"
echo ""
