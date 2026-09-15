"""Control tower aggregation endpoints."""
from __future__ import annotations

import json
from collections import Counter
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from alerts.imd import fetch_imd_cap_alerts
from p6_src.config import gemini_api_key, hf_token, p3_base_url, p4_base_url, p5_base_url
from p6_src.database import get_session
from p6_src.orm import AlertRow, IncidentRow, SimulationRow
from simulation.engine import load_shipments

router = APIRouter(prefix="/api/v1/control-tower", tags=["control-tower"])

OPEN_STATUSES = {"UNDER_VERIFICATION", "VERIFIED"}


@router.get("/overview")
def overview(db: Session = Depends(get_session)) -> dict[str, Any]:
    incidents = db.query(IncidentRow).all()
    alerts = db.query(AlertRow).all()
    sims = db.query(SimulationRow).order_by(SimulationRow.generated_at.desc()).all()
    open_incidents = [i for i in incidents if i.status in OPEN_STATUSES]
    sev = Counter(a.severity for a in alerts)
    shipments, ship_src = load_shipments()
    critical_at_risk = [
        s
        for s in shipments
        if str(s.get("priority") or "").upper() == "CRITICAL"
        and str(s.get("status") or "").upper() in {"ON_ROUTE", "PENDING", "DELAYED"}
    ]
    shipments_monitored = [
        s
        for s in shipments
        if str(s.get("status") or "").upper() not in {"DELIVERED", "CANCELLED"}
    ]
    imd = fetch_imd_cap_alerts()
    last_sim = json.loads(sims[0].result_json) if sims else None
    return {
        "open_incidents": len(open_incidents),
        "incidents_total": len(incidents),
        "incidents_by_status": dict(Counter(i.status for i in incidents)),
        "active_alerts": len(alerts),
        "alerts_by_severity": {
            "LOW": sev.get("LOW", 0),
            "MEDIUM": sev.get("MEDIUM", 0),
            "HIGH": sev.get("HIGH", 0),
            "CRITICAL": sev.get("CRITICAL", 0),
        },
        "critical_shipments_at_risk": len(critical_at_risk),
        "shipments_monitored": len(shipments_monitored),
        "imd_alert_count": len(imd),
        "last_simulation": last_sim,
        "data_provenance": {
            "incidents": "p6_sqlite",
            "alerts": "p6_sqlite",
            "shipments": ship_src,
            "imd": "https://wis2box.imd.gov.in/oapi/collections/messages/items",
            "image_verification": (
                "gemini_vision_ai"
                if gemini_api_key()
                else ("huggingface_api" if hf_token() else "visual_telemetry")
            ),
            "upstream": {
                "P3_BASE_URL": bool(p3_base_url()),
                "P4_BASE_URL": bool(p4_base_url()),
                "P5_BASE_URL": bool(p5_base_url()),
            },
        },
    }


@router.get("/map-state")
def map_state(db: Session = Depends(get_session)) -> dict[str, Any]:
    incidents = db.query(IncidentRow).filter(IncidentRow.status.in_(tuple(OPEN_STATUSES))).all()
    alerts = db.query(AlertRow).all()
    features = []
    for row in incidents:
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [row.longitude, row.latitude]},
                "properties": {
                    "incident_id": row.incident_id,
                    "incident_type": row.incident_type,
                    "detected_type": row.detected_type,
                    "status": row.status,
                    "confidence": row.confidence,
                    "road_id": row.road_id,
                },
            }
        )
    return {
        "type": "FeatureCollection",
        "features": features,
        "alert_road_ids": [a.affected_road for a in alerts if a.affected_road],
        "alerts": [
            {
                "alert_id": a.alert_id,
                "severity": a.severity,
                "affected_road": a.affected_road,
                "recommended_action": a.recommended_action,
            }
            for a in alerts
        ],
    }
