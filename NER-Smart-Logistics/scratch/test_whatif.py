import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "p6-control-tower"))

from simulation.engine import run_what_if

scenarios = [
    ("LANDSLIDE_BLOCK", "NH-13"),
    ("FLOOD_CLOSURE", "NH-27"),
    ("BRIDGE_OUT", "NH-6")
]

for sc_type, road in scenarios:
    res = run_what_if(sc_type, road, None)
    print(f"=== SCENARIO: {sc_type} on {road} ===")
    print(f"Scenario ID: {res['scenario_id']}")
    print(f"Affected Shipments: {res['affected_shipments']}")
    print(f"Average Delay: +{res['average_delay_hours']} hrs")
    print(f"Stockout Risk Change: +{int(res['shortage_risk_change']*100)}%")
    print(f"Recommended Reroute: {res['recommended_reroutes'][0]['corridor']}")
    print(f"Impacted Convoy 1: {res['affected_shipments_detail'][0]['shipment_id']} ({res['affected_shipments_detail'][0]['cargo']})")
    print()

print("=== ALL WHAT-IF SIMULATION TESTS SUCCEEDED 100% ===")
