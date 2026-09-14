import sys
from pathlib import Path

p2_root = str(Path(__file__).resolve().parents[1])
if p2_root not in sys.path:
    sys.path.insert(0, p2_root)
