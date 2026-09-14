@echo off
REM ==============================================================================
REM  PRAVAH — NER Smart Logistics Unified Platform Launcher (Windows)
REM  Integrates P1 Flood, P2 Landslide, P3 Road Risk, P4 Route Optimization,
REM  P5 Logistics, P6 Control Tower + Gemini AI + Frontend on Port 8002
REM ==============================================================================

echo.
echo ==============================================================================
echo   PRAVAH -- AI-Based Smart Logistics ^& Accessibility Intelligence Platform
echo   North Eastern Region (SIH 26002)
echo ==============================================================================
echo.

cd /d "%~dp0"

REM Check for virtual environment
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
    echo [OK] Activated local virtual environment (venv)
) else if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
    echo [OK] Activated local virtual environment (.venv)
) else (
    echo [INFO] Running using system Python
)

REM Set Environment Defaults
set P3_BASE_URL=http://127.0.0.1:8002
set P4_BASE_URL=http://127.0.0.1:8002
set P5_BASE_URL=http://127.0.0.1:8002

echo [INFO] Launching Pravah Unified Server on http://127.0.0.1:8002 ...
echo [INFO] Serving Web Dashboard and Unified Microservice APIs (P1-P6 + Gemini AI)
echo.

REM Automatically open browser after 2 seconds
start "" cmd /c "timeout /t 2 /nobreak >nul & start http://127.0.0.1:8002"

python -m uvicorn server.unified_server:app --host 127.0.0.1 --port 8002 --reload

pause
