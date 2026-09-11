"""What-if simulation API."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from simulation.engine import run_what_if
from p6_src.database import get_session
from p6_src.ids import next_id, utc_now_iso
from p6_src.orm import SimulationRow
from p6_src.schemas import WhatIfIn, WhatIfOut

router = APIRouter(prefix="/api/v1/simulation", tags=["simulation"])


@router.post("/what-if", response_model=WhatIfOut)
def what_if(body: WhatIfIn, db: Session = Depends(get_session)) -> WhatIfOut:
    scenario_id = body.scenario_id or next_id(db, SimulationRow, "scenario_id", "SCENARIO", 1)
    result = run_what_if(body.scenario_type, body.road_id, body.warehouse_id)
    result["scenario_id"] = scenario_id
    row = SimulationRow(
        scenario_id=scenario_id,
        scenario_type=body.scenario_type,
        road_id=body.road_id,
        result_json=json.dumps(result),
        generated_at=result.get("generated_at") or utc_now_iso(),
    )
    existing = db.get(SimulationRow, scenario_id)
    if existing:
        existing.scenario_type = row.scenario_type
        existing.road_id = row.road_id
        existing.result_json = row.result_json
        existing.generated_at = row.generated_at
    else:
        db.add(row)
    db.flush()
    return WhatIfOut.model_validate(result)
