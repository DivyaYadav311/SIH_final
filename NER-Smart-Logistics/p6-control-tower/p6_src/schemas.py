"""Pydantic contracts for P6 APIs."""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

RiskLevel = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
IncidentStatus = Literal["UNDER_VERIFICATION", "VERIFIED", "REJECTED", "RESOLVED"]
RecommendedAction = Literal["REROUTE", "HOLD", "MONITOR", "DISPATCH_ASSESSMENT"]


class IncidentCreate(BaseModel):
    incident_id: Optional[str] = None
    reported_by: str
    latitude: float
    longitude: float
    incident_type: str
    description: str = ""
    timestamp: Optional[str] = None
    image_url: Optional[str] = None
    road_id: Optional[str] = None
    district_id: Optional[str] = None


class IncidentPatch(BaseModel):
    status: Optional[IncidentStatus] = None
    description: Optional[str] = None


class IncidentOut(BaseModel):
    incident_id: str
    status: str
    detected_type: Optional[str] = None
    confidence: Optional[float] = None
    reported_by: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    incident_type: Optional[str] = None
    description: Optional[str] = None
    timestamp: Optional[str] = None
    image_url: Optional[str] = None
    verification_backend: Optional[str] = None
    exif_gps_mismatch: Optional[bool] = None
    exif_distance_km: Optional[float] = None
    road_id: Optional[str] = None
    district_id: Optional[str] = None


class AlertEvaluateIn(BaseModel):
    road_id: str
    flood_probability: float = Field(ge=0, le=1)
    landslide_probability: float = Field(ge=0, le=1)
    disruption_probability: float = Field(ge=0, le=1)
    accessibility_score: float = Field(ge=0, le=100)
    affected_shipments: int = 0
    critical_shipments: int = 0
    shortage_probability: float = Field(ge=0, le=1)
    affected_districts: Optional[list[str]] = None


class AlertOut(BaseModel):
    alert_id: str
    severity: RiskLevel
    title: str
    affected_road: Optional[str] = None
    affected_shipments: int = 0
    affected_districts: list[str] = Field(default_factory=list)
    recommended_action: RecommendedAction
    generated_at: str
    source: str = "P6_ENGINE"


class WhatIfIn(BaseModel):
    scenario_id: Optional[str] = None
    scenario_type: str = "ROAD_BLOCKED"
    road_id: Optional[str] = None
    warehouse_id: Optional[str] = None


class WhatIfOut(BaseModel):
    scenario_id: str
    affected_roads: list[str]
    affected_shipments: int
    delayed_shipments: int
    affected_districts: int
    additional_delay_minutes: int
    shortage_risk_change: float
    recommended_route_id: Optional[str] = None
    scenario_type: Optional[str] = None
    generated_at: Optional[str] = None
    data_provenance: Optional[dict[str, Any]] = None
