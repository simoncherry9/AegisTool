#!/usr/bin/env pwsh
# AegisWiFi - instalacion completa para Windows (PowerShell)
#   .\install.ps1               instala y levanta todo
#   .\install.ps1 -Stop         detiene los procesos
#   .\install.ps1 -InstallOnly  solo instala, no arranca servicios
param(
  [switch]$Stop,
  [switch]$InstallOnly
)

$Repo = Split-Path -Parent $MyInvocation.MyCommand.Path

# --- helpers -----------------------------------------------------------------
function Log   { Write-Host "[aegis] $args" -ForegroundColor Blue }
function Ok    { Write-Host "  ok $args" -ForegroundColor Green }
function Warn  { Write-Host "[warn] $args" -ForegroundColor Yellow }
function Err   { Write-Host "[error] $args" -ForegroundColor Red }

function Kill-Processes {
  $uvicorn = Get-CimInstance Win32_Process -Filter "Name='python.exe' AND CommandLine LIKE '%uvicorn%aegiswifi%'" -ErrorAction SilentlyContinue
  if ($uvicorn) { $uvicorn | Invoke-CimMethod -MethodName Terminate | Out-Null; Ok "backend detenido" }
  else { Warn "backend no estaba corriendo" }

  $node = Get-CimInstance Win32_Process -Filter "Name='node.exe' AND CommandLine LIKE '%vite%'" -ErrorAction SilentlyContinue
  if ($node) { $node | Invoke-CimMethod -MethodName Terminate | Out-Null; Ok "frontend detenido" }
  else { Warn "frontend no estaba corriendo" }
}

# --- stop --------------------------------------------------------------------
if ($Stop) {
  Log "deteniendo procesos AegisWiFi..."
  Kill-Processes
  return
}

# --- 1. Requisitos -----------------------------------------------------------
Log "comprobando dependencias..."
$pythonOk = (Get-Command python -ErrorAction SilentlyContinue) -or (Get-Command python3 -ErrorAction SilentlyContinue)
if (-not $pythonOk) { Err "Python no encontrado"; exit 1 }
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) { Err "npm no encontrado"; exit 1 }

python --version
npm --version
""

# --- 2. Virtualenv -----------------------------------------------------------
$venvPath = Join-Path $Repo ".venv"
$venvActivate = Join-Path $venvPath "Scripts\Activate.ps1"

if (-not (Test-Path $venvActivate)) {
  Log "creando virtualenv..."
  python -m venv $venvPath
}

Log "activando virtualenv..."
. $venvActivate

Log "actualizando pip..."
python -m pip install --upgrade pip -q

Log "instalando backend (editable)..."
pip install -e "$Repo[dev]" -q
if ($LASTEXITCODE -ne 0) { Err "fallo al instalar backend"; exit 1 }

# --- 3. .env con Fernet key -------------------------------------------------
$envFile = Join-Path $Repo ".env"
if (-not (Test-Path $envFile)) {
  Log "generando .env con clave Fernet..."
  $fernetKey = python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
  @"
# AegisWiFi - generado automaticamente por install.ps1
AEGISWIFI_ENVIRONMENT=development
AEGISWIFI_DEBUG=true
AEGISWIFI_LOG_LEVEL=DEBUG
AEGISWIFI_LOG_JSON=false
AEGISWIFI_API_HOST=127.0.0.1
AEGISWIFI_API_PORT=8001
AEGISWIFI_DATABASE__URL=
AEGISWIFI_PATHS__DATA_DIR=$Repo\data
AEGISWIFI_PATHS__EVIDENCE_DIR=$Repo\data\evidence
AEGISWIFI_SECURITY__REQUIRE_AUTH=false
AEGISWIFI_SECURITY__ENCRYPTION_KEY_B64=$fernetKey
AEGISWIFI_JOBS__MAX_WORKERS=2
AEGISWIFI_JOBS__HEARTBEAT_INTERVAL=15
AEGISWIFI_JOBS__DEFAULT_TIMEOUT=300
AEGISWIFI_JOBS__EVENT_BUFFER_SIZE=1000
AEGISWIFI_JOBS__LOG_DIR=$Repo\data\job_logs
AEGISWIFI_JOBS__PROCESS_KILL_TIMEOUT=5
"@ | Out-File -FilePath $envFile -Encoding ASCII
  Ok ".env creado con clave Fernet"
} else {
  Log ".env ya existe, se conserva"
}

# --- 4. Directorios de datos ------------------------------------------------
Log "creando directorios de datos..."
@("data\evidence", "data\job_logs", "data\hashes") | ForEach-Object {
  $dir = Join-Path $Repo $_
  if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
}

# --- 5. Frontend ------------------------------------------------------------
Log "instalando dependencias del frontend..."
Push-Location (Join-Path $Repo "frontend")
try {
  npm install --silent
  if ($LASTEXITCODE -ne 0) { throw "npm install fallo" }
} finally { Pop-Location }

# --- 6. Migraciones ---------------------------------------------------------
Log "aplicando migraciones de base de datos..."
python -m alembic -c "$Repo\backend\alembic.ini" upgrade head
if ($LASTEXITCODE -eq 0) {
  Ok "migraciones aplicadas"
} else {
  Warn "alembic fallo - ejecuta manualmente: python -m alembic -c backend\alembic.ini upgrade head"
}

# --- 7. Diagnostico ---------------------------------------------------------
Log "verificando instalacion..."
python -c "import aegiswifi; print('  aegiswifi', aegiswifi.__version__)"
if ($LASTEXITCODE -ne 0) { Err "no se pudo importar aegiswifi - revisa la instalacion"; exit 1 }
Ok "instalacion completada"
""

# --- 8. Arrancar servicios --------------------------------------------------
if ($InstallOnly) {
  Log "InstallOnly: no se arrancan los servicios."
  Write-Host "`nEjecuta despues: start_backend.bat  y  start_frontend.bat`n"
  return
}

Log "iniciando servicios..."

Kill-Processes

# Backend - script lanzador temporal
$backendLog = Join-Path $Repo "data\backend.log"
$backendScript = Join-Path $Repo "data\_run_backend.ps1"
Log "  > backend  en http://127.0.0.1:8001"
@"
`$log = '$backendLog'
try {
  . '$venvActivate'
  Start-Transcript -Path `$log -Append
  python -m uvicorn aegiswifi.main:app --host 127.0.0.1 --port 8001 --reload --log-level info
  Stop-Transcript
} catch {
  `"Error: `$_`" | Out-File `$log -Append
  Read-Host "Error - presiona Enter"
}
"@ | Out-File -FilePath $backendScript -Encoding ASCII

Start-Process -WindowStyle Minimized -FilePath "powershell" -ArgumentList "-NoExit", "-File", $backendScript
Ok "backend lanzado"

# Frontend - script lanzador temporal
$frontendLog = Join-Path $Repo "data\frontend.log"
$frontendScript = Join-Path $Repo "data\_run_frontend.ps1"
$frontendDir = Join-Path $Repo "frontend"
Log "  > frontend en http://127.0.0.1:5173"
@"
`$log = '$frontendLog'
try {
  Set-Location '$frontendDir'
  Start-Transcript -Path `$log -Append
  npm run dev
  Stop-Transcript
} catch {
  `"Error: `$_`" | Out-File `$log -Append
  Read-Host "Error - presiona Enter"
}
"@ | Out-File -FilePath $frontendScript -Encoding ASCII

Start-Process -WindowStyle Minimized -FilePath "powershell" -ArgumentList "-NoExit", "-File", $frontendScript
Ok "frontend lanzado"

Start-Sleep -Seconds 4

Clear-Host
Write-Host @"

  ===============================================================
   AegisWiFi esta corriendo

   Frontend :  http://127.0.0.1:5173
   Backend  :  http://127.0.0.1:8001
   API docs :  http://127.0.0.1:8001/docs

   Logs: data\backend.log  /  data\frontend.log
   Para detener: .\install.ps1 -Stop
  ===============================================================

"@
