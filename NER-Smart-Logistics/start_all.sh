#!/bin/bash
# ==============================================================================
# PRAVAH — Start All Microservices & Frontend
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [ -d "$SCRIPT_DIR/p4-path-optimization" ]; then
    ROOT_DIR="$SCRIPT_DIR"
else
    ROOT_DIR="$SCRIPT_DIR/NER-Smart-Logistics"
fi
echo "Starting PRAVAH services from: $ROOT_DIR"

# Kill any existing processes on the required ports
echo "Checking and freeing ports..."
lsof -ti :3000 -ti :8001 -ti :8002 -ti :8005 -ti :8006 | xargs kill -9 2>/dev/null || true
sleep 1

# 1. P4 — Route Optimization & Road Network
echo "Starting P4 (Path Optimization) on port 8001..."
(cd "$ROOT_DIR/p4-path-optimization" && python -m uvicorn p4_src.main:app --host 127.0.0.1 --port 8001) &
PID_P4=$!

# 2. P5 — Logistics & Supply Chain
echo "Starting P5 (Logistics) on port 8005..."
(cd "$ROOT_DIR/p5-logistics" && PYTHONPATH=. python -m uvicorn p5_src.main:app --host 127.0.0.1 --port 8005) &
PID_P5=$!

# 3. P6 — Control Tower & Disruption Simulator
echo "Starting P6 (Control Tower) on port 8006..."
(cd "$ROOT_DIR/p6-control-tower" && python -m uvicorn p6_src.main:app --host 127.0.0.1 --port 8006) &
PID_P6=$!

# 4. P2 — Landslide & Hazard Intelligence
echo "Starting P2 (Landslide Intelligence) on port 8002..."
(cd "$ROOT_DIR/p2-landslide" && python -m uvicorn app.main:app --host 127.0.0.1 --port 8002) &
PID_P2=$!

# 5. Frontend UI
echo "Starting Frontend Web Server on port 3000..."
(cd "$ROOT_DIR" && python -m http.server 3000 --directory Frontend) &
PID_FE=$!

echo ""
echo "=============================================================================="
echo "  PRAVAH SERVICES ARE NOW LIVE:"
echo "  - Frontend Dashboard:    http://127.0.0.1:3000"
echo "  - P4 Path Optimization:  http://127.0.0.1:8001/docs"
echo "  - P5 Logistics Engine:   http://127.0.0.1:8005/docs"
echo "  - P6 Control Tower:      http://127.0.0.1:8006/docs"
echo "  - P2 Hazard Pipeline:    http://127.0.0.1:8002/docs"
echo "=============================================================================="
echo "Press Ctrl+C to stop all servers."

trap "kill $PID_P4 $PID_P5 $PID_P6 $PID_P2 $PID_FE 2>/dev/null; exit 0" INT TERM
wait
