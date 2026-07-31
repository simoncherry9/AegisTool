@echo off
REM AegisWiFi — instalación para Windows (CMD)
REM   install.bat          instala y levanta todo
REM   install.bat --stop   detiene los procesos
setlocal
cd /d "%~dp0"
set "REPO=%~dp0"
set "REPO=%REPO:~0,-1%"

if /i "%1"=="--stop" goto :stop

:: ─── 1. Requisitos ───────────────────────────────────────────────────────────
echo [aegis] comprobando dependencias...
where python >nul 2>&1 || ( echo [error] Python no encontrado & pause & goto :eof )
where npm >nul 2>&1 || ( echo [error] npm no encontrado & pause & goto :eof )
python --version
npm --version
echo.

:: ─── 2. Virtualenv ───────────────────────────────────────────────────────────
if not exist "%REPO%\.venv\Scripts\activate.bat" (
  echo [aegis] creando virtualenv...
  python -m venv "%REPO%\.venv"
)
call "%REPO%\.venv\Scripts\activate.bat"
echo [aegis] actualizando pip...
python -m pip install --upgrade pip -q
echo [aegis] instalando backend (editable)...
pip install -e "%REPO%[dev]" -q
if %ERRORLEVEL% neq 0 ( echo [error] fallo al instalar backend & pause & goto :eof )

:: ─── 3. .env con Fernet key (sin ENABLEDELAYEDEXPANSION) ────────────────────
if not exist "%REPO%\.env" (
  echo [aegis] generando .env con clave Fernet...
  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" > "%TEMP%\aegis_fernet.key"
  set /p FERNET=<"%TEMP%\aegis_fernet.key"
  del "%TEMP%\aegis_fernet.key"
  echo # AegisWiFi > "%REPO%\.env"
  echo AEGISWIFI_ENVIRONMENT=development >> "%REPO%\.env"
  echo AEGISWIFI_DEBUG=true >> "%REPO%\.env"
  echo AEGISWIFI_LOG_LEVEL=DEBUG >> "%REPO%\.env"
  echo AEGISWIFI_LOG_JSON=false >> "%REPO%\.env"
  echo AEGISWIFI_API_HOST=127.0.0.1 >> "%REPO%\.env"
  echo AEGISWIFI_API_PORT=8001 >> "%REPO%\.env"
  echo AEGISWIFI_DATABASE__URL= >> "%REPO%\.env"
  echo AEGISWIFI_PATHS__DATA_DIR=%REPO%\data >> "%REPO%\.env"
  echo AEGISWIFI_PATHS__EVIDENCE_DIR=%REPO%\data\evidence >> "%REPO%\.env"
  echo AEGISWIFI_SECURITY__REQUIRE_AUTH=false >> "%REPO%\.env"
  echo AEGISWIFI_SECURITY__ENCRYPTION_KEY_B64=%FERNET% >> "%REPO%\.env"
  echo AEGISWIFI_JOBS__MAX_WORKERS=2 >> "%REPO%\.env"
  echo AEGISWIFI_JOBS__HEARTBEAT_INTERVAL=15 >> "%REPO%\.env"
  echo AEGISWIFI_JOBS__DEFAULT_TIMEOUT=300 >> "%REPO%\.env"
  echo AEGISWIFI_JOBS__EVENT_BUFFER_SIZE=1000 >> "%REPO%\.env"
  echo AEGISWIFI_JOBS__LOG_DIR=%REPO%\data\job_logs >> "%REPO%\.env"
  echo AEGISWIFI_JOBS__PROCESS_KILL_TIMEOUT=5 >> "%REPO%\.env"
  echo   ok .env creado con clave Fernet
) else (
  echo [aegis] .env ya existe, se conserva
)

:: ─── 4. Directorios ─────────────────────────────────────────────────────────
echo [aegis] creando directorios de datos...
if not exist "%REPO%\data\evidence" mkdir "%REPO%\data\evidence"
if not exist "%REPO%\data\job_logs" mkdir "%REPO%\data\job_logs"
if not exist "%REPO%\data\hashes" mkdir "%REPO%\data\hashes"

:: ─── 5. Frontend ─────────────────────────────────────────────────────────────
echo [aegis] instalando dependencias del frontend...
pushd "%REPO%\frontend"
call npm install --silent
if %ERRORLEVEL% neq 0 ( echo [error] npm install fallo & popd & pause & goto :eof )
popd

:: ─── 6. Migraciones ──────────────────────────────────────────────────────────
echo [aegis] aplicando migraciones de base de datos...
python -m alembic -c "%REPO%\backend\alembic.ini" upgrade head
if %ERRORLEVEL% equ 0 ( echo   ok migraciones aplicadas ) else ( echo [warn] alembic fallo & pause & goto :eof )

:: ─── 7. Diagnóstico ──────────────────────────────────────────────────────────
echo [aegis] verificando instalacion...
python -c "import aegiswifi; print('  aegiswifi', aegiswifi.__version__)"
if %ERRORLEVEL% neq 0 ( echo [error] no se pudo importar aegiswifi & pause & goto :eof )
echo   ok instalacion completada
echo.

:: ─── 8. Arrancar ─────────────────────────────────────────────────────────────
echo [aegis] iniciando servicios...
echo.
echo  IMPORTANTE: Esto abre DOS ventanas nuevas minimizadas.
echo  Si no ves las ventanas, revisa la barra de tareas.
echo.

:: Detener previos
call :kill_processes >nul 2>&1

:: Backend
echo [aegis]   ^> backend  en http://127.0.0.1:8001
echo [aegis]   ^> logs: data\backend.log
start "AegisWiFi Backend" /MIN cmd /c "cd /d \"%REPO%\" && call .venv\Scripts\activate.bat && python -m uvicorn aegiswifi.main:app --host 127.0.0.1 --port 8001 --reload --log-level info >> \"%REPO%\data\backend.log\" 2>&1"

:: Frontend
echo [aegis]   ^> frontend en http://127.0.0.1:5173
echo [aegis]   ^> logs: data\frontend.log
start "AegisWiFi Frontend" /MIN cmd /c "cd /d \"%REPO%\frontend\" && npm run dev >> \"%REPO%\data\frontend.log\" 2>&1"

timeout /t 4 /nobreak >nul

echo.
echo   ===============================================================
echo    AegisWiFi esta corriendo
echo.
echo    Frontend :  http://127.0.0.1:5173
echo    Backend  :  http://127.0.0.1:8001
echo    API docs :  http://127.0.0.1:8001/docs
echo.
echo    Logs: data\backend.log  /  data\frontend.log
echo    Para detener: install.bat --stop
echo.
echo    NOTA: Los servicios corren en ventanas minimizadas.
echo    Si algo falla, revisa los logs o ejecuta:
echo      start_backend.bat   (ventana visible con errores)
echo      start_frontend.bat  (ventana visible con errores)
echo   ===============================================================
echo.
pause
goto :eof

:: ─── stop ────────────────────────────────────────────────────────────────────
:stop
echo [aegis] deteniendo procesos AegisWiFi...
call :kill_processes
echo.
pause
goto :eof

:kill_processes
taskkill /FI "WINDOWTITLE eq AegisWiFi Backend*" /F >nul 2>&1 && ( echo   ok backend detenido ) || ( echo [warn] backend no estaba corriendo )
taskkill /FI "WINDOWTITLE eq AegisWiFi Frontend*" /F >nul 2>&1 && ( echo   ok frontend detenido ) || ( echo [warn] frontend no estaba corriendo )
exit /b 0
