@echo off
REM AegisWiFi — Lanzador del frontend (se queda abierto para mostrar errores)
cd /d "%~dp0\frontend"
echo [aegis] Starting frontend on http://127.0.0.1:5173
echo.
npm run dev 2>&1
echo.
echo [ERROR] El frontend se cerro. Revisa el mensaje de arriba.
pause
