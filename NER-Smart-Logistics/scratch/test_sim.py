import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "p6-control-tower"))

from simulation.engine import run_what_if

res = run_what_if("LANDSLIDE_BLOCK", "NH-13", None)
print("=== SIMULATION RESULT ===")
import json
print(json.dumps(res, indent=2))
