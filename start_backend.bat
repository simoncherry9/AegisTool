@echo off
REM AegisWiFi — Lanzador del backend (se queda abierto para mostrar errores)
cd /d "%~dp0"
call .venv\Scripts\activate.bat
echo [aegis] Starting backend on http://127.0.0.1:8001
echo [aegis] Logs: data\backend.log
echo.
python -m uvicorn aegiswifi.main:app --host 127.0.0.1 --port 8001 --reload --log-level info 2>&1
echo.
echo [ERROR] El backend se cerro. Revisa el mensaje de arriba.
pause
