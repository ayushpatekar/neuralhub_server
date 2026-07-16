@echo off
title NeuralHub Client
cd /d "%~dp0"
color 0B

echo.
echo  =============================================
echo   NeuralHub  --  Trainer Client
echo  =============================================
echo.

where python >nul 2>&1
if %errorlevel% neq 0 (
    echo  ERROR: Python not found.
    echo  Install from https://www.python.org/downloads/
    echo  Tick "Add Python to PATH" during install.
    pause
    exit /b 1
)

echo  Installing / checking dependencies...
pip install flask torch pandas requests scikit-learn joblib numpy --quiet --disable-pip-version-check
if %errorlevel% neq 0 (
    echo.
    echo  WARNING: Some packages may have failed to install.
    echo  Trying to continue anyway...
    echo.
)

REM ── Auto-patch SERVER_URL if still placeholder ──────────────────────────────
python -c "txt=open('app.py').read(); print('NEEDS_URL') if 'YOUR_NGROK_URL_HERE' in txt else None" > "%TEMP%\nh_check.txt" 2>&1
set /p NB_CHECK=<"%TEMP%\nh_check.txt"

if "%NB_CHECK%"=="NEEDS_URL" (
    echo  You need to set your ngrok URL first.
    echo  1. Run run_server.bat
    echo  2. Open http://localhost:4040 in your browser
    echo  3. Copy the  https://xxxx.ngrok-free.app  URL
    echo.
    set /p NGROK_URL="  Paste your ngrok URL here and press Enter: "
    python -c "import sys; url=sys.argv[1].strip().rstrip('/'); txt=open('app.py').read(); txt=txt.replace('https://YOUR_NGROK_URL_HERE.ngrok-free.app',url); open('app.py','w').write(txt); print('URL saved.')" "%NGROK_URL%"
    echo  Done. Starting client...
    echo.
)

echo  =============================================
echo   Opening http://localhost:5000
echo   DO NOT close this window.
echo  =============================================
echo.

python app.py
set EXIT_CODE=%errorlevel%

echo.
if exist client_error.log (
    echo  --- Error Log ---
    type client_error.log
    echo  -----------------
)
if %EXIT_CODE% neq 0 (
    echo.
    echo  Client exited with error code %EXIT_CODE%
    echo  If you see an ImportError, run this to fix:
    echo    pip install flask torch pandas requests scikit-learn joblib numpy
)
echo.
pause
