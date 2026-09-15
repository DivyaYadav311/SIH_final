#!/bin/bash
# ==============================================================================
# PRAVAH — NER Smart Logistics Unified Platform Launcher (macOS / Linux)
# Launches Unified Backend (P1–P6 + Gemini AI + Telemetry) and Frontend
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR/NER-Smart-Logistics"

cd "$PROJECT_DIR" || exit 1

echo "=============================================================================="
echo "  PRAVAH -- AI-Based Smart Logistics & Accessibility Intelligence Platform"
echo "  North Eastern Region (SIH 26002)"
echo "=============================================================================="
echo ""
echo "[INFO] Freeing ports 8002 and 3000 if occupied..."
lsof -ti :8002 -ti :3000 | xargs kill -9 2>/dev/null || true
sleep 1

echo "[INFO] Launching Pravah Unified Server on http://127.0.0.1:8002 ..."
echo "[INFO] Serving Web Dashboard, Driver Portal, and Unified APIs (P1-P6)"
echo ""

# Start frontend static server on port 3000 in background as well for dual-port access
python3 -m http.server 3000 --directory Frontend &
PID_FE=$!

trap "kill $PID_FE 2>/dev/null; exit 0" INT TERM

python3 -m uvicorn server.unified_server:app --host 127.0.0.1 --port 8002 --reload
