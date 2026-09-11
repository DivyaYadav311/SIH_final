@echo off
REM ============================================================
REM  Pravah — NER Smart Logistics Unified Server Launcher
REM  Starts the unified backend on http://127.0.0.1:8002
REM ============================================================

echo.
echo  =============================================
echo   Pravah — Unified NER Smart Logistics Server
echo   Starting on http://127.0.0.1:8002
echo  =============================================
echo.

cd /d "%~dp0.."

REM Activate venv if it exists
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
    echo  [OK] Virtual environment activated.
) else if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
    echo  [OK] Virtual environment activated.
) else (
    echo  [WARN] No venv found. Using system Python.
)

echo.
echo  Installing dependencies...
pip install -r server\requirements.txt --quiet 2>nul

echo.
echo  Launching Pravah Unified Server...
echo  Open http://127.0.0.1:8002 in your browser
echo.

python -m uvicorn server.unified_server:app --host 127.0.0.1 --port 8002 --reload

pause
