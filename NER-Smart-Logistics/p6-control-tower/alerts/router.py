"""Alert evaluate, list, and official IMD CAP endpoints."""
from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from alerts.engine import evaluate_severity
from alerts.imd import fetch_imd_cap_alerts
from p6_src.database import get_session
from p6_src.hub import broadcast_alert_sync
from p6_src.ids import next_id, utc_now_iso
from p6_src.orm import AlertRow
from p6_src.schemas import AlertEvaluateIn, AlertOut

router = APIRouter(prefix="/api/v1/alerts", tags=["alerts"])


def _districts(row: AlertRow) -> list[str]:
    try:
        value = json.loads(row.affected_districts_json or "[]")
        return value if isinstance(value, list) else []
    except json.JSONDecodeError:
        return []


def _to_out(row: AlertRow) -> AlertOut:
    return AlertOut(
        alert_id=row.alert_id,
        severity=row.severity,  # type: ignore[arg-type]
        title=row.title,
        affected_road=row.affected_road,
        affected_shipments=row.affected_shipments,
        affected_districts=_districts(row),
        recommended_action=row.recommended_action,  # type: ignore[arg-type]
        generated_at=row.generated_at,
        source=row.source,
    )


@router.post("/evaluate", response_model=AlertOut)
def evaluate_alert(body: AlertEvaluateIn, db: Session = Depends(get_session)) -> AlertOut:
    severity, action, title = evaluate_severity(body)
    alert_id = next_id(db, AlertRow, "alert_id", "ALERT", 501)
    districts = body.affected_districts or []
    row = AlertRow(
        alert_id=alert_id,
        severity=severity,
        title=title,
        affected_road=body.road_id,
        affected_shipments=body.affected_shipments,
        affected_districts_json=json.dumps(districts),
        recommended_action=action,
        generated_at=utc_now_iso(),
        source="P6_ENGINE",
        payload_json=body.model_dump_json(),
    )
    db.add(row)
    db.flush()
    out = _to_out(row)
    broadcast_alert_sync(out.model_dump())
    return out


@router.get("", response_model=list[AlertOut])
def list_alerts(
    db: Session = Depends(get_session),
    include_imd: bool = Query(default=False),
) -> list[dict[str, Any]]:
    stored = [_to_out(r).model_dump() for r in db.query(AlertRow).order_by(AlertRow.generated_at.desc()).all()]
    if not include_imd:
        return stored
    for i, cap in enumerate(fetch_imd_cap_alerts(), start=1):
        stored.append(
            {
                "alert_id": f"IMD_{i:04d}",
                "severity": cap.get("risk_level", "LOW"),
                "title": cap.get("headline") or cap.get("event") or "IMD warning",
                "affected_road": None,
                "affected_shipments": 0,
                "affected_districts": [cap["area"]] if cap.get("area") else [],
                "recommended_action": "MONITOR",
                "generated_at": utc_now_iso(),
                "source": "IMD_CAP",
            }
        )
    return stored


@router.get("/imd")
def imd_alerts() -> dict[str, Any]:
    alerts = fetch_imd_cap_alerts()
    return {
        "count": len(alerts),
        "source": "https://wis2box.imd.gov.in/oapi/collections/messages/items",
        "alerts": alerts,
    }
