@echo off
title NeuralHub Server
cd /d "%~dp0"
color 0A

echo.
echo  =============================================
echo   NeuralHub  --  Server
echo   Starting up...
echo  =============================================
echo.

pip install fastapi "uvicorn[standard]" torch pandas requests scikit-learn joblib --quiet --disable-pip-version-check >nul 2>&1
pip install fastapi uvicorn torch pandas requests scikit-learn joblib --quiet --disable-pip-version-check >nul 2>&1

where ollama >nul 2>&1
if %errorlevel% equ 0 (
    start "" /min ollama serve
    timeout /t 2 /nobreak >nul
    ollama pull phi3:mini >nul 2>&1
)

where ngrok >nul 2>&1
if %errorlevel% equ 0 (
    start "ngrok" cmd /k "ngrok http 8000"
)

echo  Server log is being saved to: server_error.log
echo  If the window closes, open server_error.log to see the error.
echo.
echo  =============================================
echo   Server running at http://localhost:8000
echo   DO NOT close this window.
echo  =============================================
echo.

python server.py 2> server_error.log

echo.
echo  *** SERVER CRASHED OR STOPPED ***
echo.
echo  Error saved to server_error.log
echo  Opening it now...
echo.
type server_error.log
echo.
pause
