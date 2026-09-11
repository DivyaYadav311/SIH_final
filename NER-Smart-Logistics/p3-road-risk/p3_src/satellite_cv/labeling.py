from __future__ import annotations

from typing import Any


def assess_physical_road_status(
    changed_fraction: float | None,
    before_available: bool,
    after_available: bool,
    days_before: int | None,
    days_after: int | None,
    resolution_m: float | None = None,
    cloud_affected: bool = False,
    background_mean: float | None = None,
    corridor_mean: float | None = None,
    geometry_source: str = "coordinate_buffer",
) -> dict[str, Any]:
    evidence: list[str] = []
    manual_review = geometry_source != "osm_overpass"
    if not before_available or not after_available:
        return {"physical_road_status": "UNCERTAIN", "disruption_confidence": 0.0, "manual_review_required": True, "reason": "missing_before_after_pair"}
    if cloud_affected:
        return {"physical_road_status": "UNCERTAIN", "disruption_confidence": 0.1, "manual_review_required": True, "reason": "cloud_affected"}
    if resolution_m is not None and resolution_m > 20:
        return {"physical_road_status": "UNCERTAIN", "disruption_confidence": 0.15, "manual_review_required": True, "reason": "insufficient_resolution"}
    if days_before is None or days_after is None or days_before > 30 or days_after > 14:
        return {"physical_road_status": "UNCERTAIN", "disruption_confidence": 0.2, "manual_review_required": True, "reason": "temporal_gap_too_large"}
    if changed_fraction is None:
        return {"physical_road_status": "UNCERTAIN", "disruption_confidence": 0.2, "manual_review_required": True, "reason": "no_valid_corridor_pixels"}
    if background_mean is not None and corridor_mean is not None and corridor_mean <= background_mean * 1.1:
        return {"physical_road_status": "UNCERTAIN", "disruption_confidence": 0.25, "manual_review_required": True, "reason": "change_not_concentrated_on_road"}
    if changed_fraction >= 0.60:
        evidence.append("large localized corridor change")
        return {"physical_road_status": "DISRUPTED", "disruption_confidence": min(0.95, 0.5 + changed_fraction / 2) * (0.75 if manual_review else 1.0), "manual_review_required": True, "reason": "; ".join(evidence) + ("; coordinate fallback" if manual_review else "")}
    if changed_fraction <= 0.20:
        return {"physical_road_status": "OPEN", "disruption_confidence": min(0.90, 0.55 + (0.20 - changed_fraction)) * (0.75 if manual_review else 1.0), "manual_review_required": manual_review, "reason": "corridor remains materially consistent"}
    return {"physical_road_status": "UNCERTAIN", "disruption_confidence": 0.4, "manual_review_required": True, "reason": "ambiguous_corridor_change"}