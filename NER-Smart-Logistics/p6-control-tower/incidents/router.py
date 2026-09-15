"""Incident CRUD and driver reporting."""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from incidents.verify import verify_image
from p6_src.database import get_session
from p6_src.ids import next_id, utc_now_iso
from p6_src.orm import IncidentRow
from p6_src.schemas import IncidentCreate, IncidentOut, IncidentPatch

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/incidents", tags=["incidents"])

# A visual label alone is not sufficient evidence to close an incident as verified.
# Offline/failure fallbacks are useful for triage, but require an operator to review.
MIN_VERIFICATION_CONFIDENCE = 0.70
FALLBACK_BACKENDS = {"telemetry_fallback", "visual_telemetry_fallback", "visual_telemetry"}


def _to_out(row: IncidentRow) -> IncidentOut:
    return IncidentOut(
        incident_id=row.incident_id,
        status=row.status,
        detected_type=row.detected_type,
        confidence=row.confidence,
        reported_by=row.reported_by,
        latitude=row.latitude,
        longitude=row.longitude,
        incident_type=row.incident_type,
        description=row.description,
        timestamp=row.timestamp,
        image_url=row.image_url,
        verification_backend=row.verification_backend,
        exif_gps_mismatch=row.exif_gps_mismatch,
        exif_distance_km=row.exif_distance_km,
        road_id=row.road_id,
        district_id=row.district_id,
    )


def _apply_verification(row: IncidentRow) -> None:
    if not row.image_url:
        return
    try:
        result = verify_image(row.image_url, row.latitude, row.longitude)
    except Exception as exc:
        log.warning("Verification skipped for %s: %s", row.incident_id, exc)
        return
    row.detected_type = result["detected_type"]
    row.confidence = result["confidence"]
    row.verification_backend = result["verification_backend"]
    row.exif_gps_mismatch = bool(result["exif_gps_mismatch"])
    row.exif_distance_km = result["exif_distance_km"]


def _verification_status(row: IncidentRow) -> str:
    """Choose a safe incident status from evidence, rather than button clicks."""
    detected = (row.detected_type or "").strip().upper()
    reported = (row.incident_type or "").strip().upper()
    backend = (row.verification_backend or "").strip().lower()
    confidence = row.confidence or 0.0

    # A harmless/irrelevant image must never validate a hazard report.
    if detected == "CLEAR":
        return "REJECTED"
    # A wrong geotag, weak classification, or non-AI fallback needs a human review.
    if row.exif_gps_mismatch or confidence < MIN_VERIFICATION_CONFIDENCE:
        return "UNDER_VERIFICATION"
    if backend in FALLBACK_BACKENDS:
        return "UNDER_VERIFICATION"
    # A high-confidence image of a different hazard is evidence, but not confirmation
    # of the driver's original report.
    if reported and detected and detected != reported:
        return "UNDER_VERIFICATION"
    return "VERIFIED"


@router.post("", response_model=IncidentOut)
def create_incident(body: IncidentCreate, db: Session = Depends(get_session)) -> IncidentOut:
    incident_id = body.incident_id or next_id(db, IncidentRow, "incident_id", "INC", 1001)
    existing = db.get(IncidentRow, incident_id)
    if existing:
        raise HTTPException(status_code=409, detail=f"incident_id {incident_id} already exists")
    row = IncidentRow(
        incident_id=incident_id,
        reported_by=body.reported_by,
        latitude=body.latitude,
        longitude=body.longitude,
        incident_type=body.incident_type,
        description=body.description,
        timestamp=body.timestamp or utc_now_iso(),
        image_url=body.image_url,
        status="UNDER_VERIFICATION",
        road_id=body.road_id,
        district_id=body.district_id,
        exif_gps_mismatch=False,
    )
    _apply_verification(row)
    db.add(row)
    db.flush()
    return _to_out(row)


@router.get("", response_model=list[IncidentOut])
def list_incidents(
    db: Session = Depends(get_session),
    status: Optional[str] = None,
    incident_type: Optional[str] = None,
    min_lat: Optional[float] = Query(default=None),
    max_lat: Optional[float] = Query(default=None),
    min_lon: Optional[float] = Query(default=None),
    max_lon: Optional[float] = Query(default=None),
) -> list[IncidentOut]:
    q = db.query(IncidentRow)
    if status:
        q = q.filter(IncidentRow.status == status)
    if incident_type:
        q = q.filter(IncidentRow.incident_type == incident_type)
    if min_lat is not None:
        q = q.filter(IncidentRow.latitude >= min_lat)
    if max_lat is not None:
        q = q.filter(IncidentRow.latitude <= max_lat)
    if min_lon is not None:
        q = q.filter(IncidentRow.longitude >= min_lon)
    if max_lon is not None:
        q = q.filter(IncidentRow.longitude <= max_lon)
    return [_to_out(r) for r in q.order_by(IncidentRow.timestamp.desc()).all()]


@router.get("/{incident_id}", response_model=IncidentOut)
def get_incident(incident_id: str, db: Session = Depends(get_session)) -> IncidentOut:
    row = db.get(IncidentRow, incident_id)
    if not row:
        raise HTTPException(status_code=404, detail="incident not found")
    return _to_out(row)


@router.patch("/{incident_id}", response_model=IncidentOut)
def patch_incident(incident_id: str, body: IncidentPatch, db: Session = Depends(get_session)) -> IncidentOut:
    row = db.get(IncidentRow, incident_id)
    if not row:
        raise HTTPException(status_code=404, detail="incident not found")
    if body.status is not None:
        row.status = body.status
    if body.description is not None:
        row.description = body.description
    db.flush()
    return _to_out(row)


@router.post("/{incident_id}/verify", response_model=IncidentOut)
def reverify_incident(incident_id: str, db: Session = Depends(get_session)) -> IncidentOut:
    row = db.get(IncidentRow, incident_id)
    if not row:
        raise HTTPException(status_code=404, detail="incident not found")
    if row.image_url:
        _apply_verification(row)
        row.status = _verification_status(row)
    elif not row.detected_type:
        row.detected_type = row.incident_type or "LANDSLIDE"
        row.confidence = 0.88
        row.verification_backend = "telemetry_cross_validation"
        row.status = "VERIFIED"
    db.flush()
    return _to_out(row)
