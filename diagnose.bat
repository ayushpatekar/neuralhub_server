@echo off
title NeuralHub Diagnostics
cd /d "%~dp0"
echo.
echo  ============================================
echo   NeuralHub Diagnostics
echo  ============================================
echo.

echo [1] Checking Python...
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo  FAIL: Python not found. Install from https://www.python.org/downloads/
    echo        Tick "Add Python to PATH" during install.
) else (
    python --version
    echo  OK
)
echo.

echo [2] Checking pip...
python -m pip --version >nul 2>&1
if %errorlevel% neq 0 (
    echo  FAIL: pip not working
) else (
    echo  OK
)
echo.

echo [3] Installing server dependencies...
pip install fastapi uvicorn torch pandas requests scikit-learn joblib
echo.

echo [4] Checking server.py imports...
python -c "import fastapi; print('  fastapi OK')"
python -c "import uvicorn; print('  uvicorn OK')"
python -c "import torch; print('  torch OK')"
python -c "import pandas; print('  pandas OK')"
python -c "import sklearn; print('  scikit-learn OK')"
python -c "import joblib; print('  joblib OK')"
echo.

echo [5] Test-loading server.py (syntax check)...
python -c "
import ast, sys
try:
    ast.parse(open('server.py').read())
    print('  server.py syntax: OK')
except SyntaxError as e:
    print(f'  server.py SYNTAX ERROR: {e}')
    sys.exit(1)
"
echo.

echo [6] Checking port 8000...
netstat -an | findstr ":8000" >nul 2>&1
if %errorlevel% equ 0 (
    echo  WARNING: Port 8000 already in use. Another server may be running.
    echo  Kill it in Task Manager or restart your PC.
) else (
    echo  Port 8000 is free. OK
)
echo.

echo  ============================================
echo   Done. Read any FAIL or ERROR lines above.
echo   Take a screenshot and share it if stuck.
echo  ============================================
echo.
pause
