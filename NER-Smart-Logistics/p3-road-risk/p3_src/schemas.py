from typing import Any, Dict, List, Optional
import math

from pydantic import BaseModel, ConfigDict, Field, field_validator
from datetime import datetime

class Geometry(BaseModel):
    type: str = Field(..., description="e.g. LineString")
    coordinates: List[List[float]] = Field(..., description="Array of [longitude, latitude] pairs")

class RoadSegment(BaseModel):
    road_id: str
    osm_way_id: Optional[str] = None
    geometry: Optional[Geometry] = None
    road_class: Optional[str] = None
    length_m: Optional[float] = None
    surface: Optional[str] = None
    lanes: Optional[int] = None
    maxspeed_kph: Optional[float] = None
    bridge: Optional[bool] = False
    tunnel: Optional[bool] = False
    oneway: Optional[bool] = False
    access: Optional[str] = None
    elevation_m: Optional[float] = None

class HazardContext(BaseModel):
    road_id: str
    flood_probability: float = Field(..., ge=0.0, le=1.0)
    landslide_probability: float = Field(..., ge=0.0, le=1.0)

class Incident(BaseModel):
    incident_id: str
    road_id: str
    type: str
    severity: int = Field(..., ge=1, le=5)
    status: str
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
    reported_at: datetime

class RoadRiskRequest(BaseModel):
    request_id: str
    timestamp: datetime
    roads: List[RoadSegment]
    hazard_context: Optional[List[HazardContext]] = []
    incidents: Optional[List[Incident]] = []

class Factors(BaseModel):
    flood_probability: float
    landslide_probability: float
    active_incident_count: int
    max_incident_severity: int

class AnalyzedRoad(BaseModel):
    road_id: str
    disruption_probability: float = Field(..., ge=0.0, le=1.0)
    accessibility_score: float = Field(..., ge=0.0, le=100.0)
    risk_level: str
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    recommended_status: str
    factors: Factors
    explanation: List[str]

class RoadRiskResponse(BaseModel):
    request_id: str
    timestamp: datetime
    model_version: str
    roads: List[AnalyzedRoad]

class P3PredictionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    road_id: str
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
    timestamp: datetime
    hour: Optional[int] = Field(None, ge=0, le=23)
    is_weekend: Optional[int] = Field(None, ge=0, le=1)
    lanes: Optional[float] = None
    traffic_signal: Optional[int] = Field(None, ge=0, le=1)
    temperature: Optional[float] = None
    vehicles_involved: Optional[float] = None
    casualties: Optional[float] = None
    is_peak_hour: Optional[int] = Field(None, ge=0, le=1)
    road_type: Optional[str] = None
    weather: Optional[str] = None
    visibility: Optional[str] = None
    traffic_density: Optional[str] = None
    cause: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    rainfall_24h: Optional[float] = None
    rainfall_3d: Optional[float] = None
    rainfall_7d: Optional[float] = None
    nearest_landslide_distance_km: Optional[float] = None
    nearby_landslide_count: Optional[float] = None
    nearest_river_distance_km: Optional[float] = None
    flood_probability: Optional[float] = Field(None, ge=0.0, le=1.0)
    landslide_probability: Optional[float] = Field(None, ge=0.0, le=1.0)
    incident_risk: Optional[float] = Field(None, ge=0.0, le=1.0)
    rainfall_intensity_factor: Optional[float] = Field(None, ge=0.0, le=1.0)
    river_level_factor: Optional[float] = Field(None, ge=0.0, le=1.0)
    slope_factor: Optional[float] = Field(None, ge=0.0, le=1.0)
    terrain_susceptibility_factor: Optional[float] = Field(None, ge=0.0, le=1.0)
    flood_vulnerability_factor: Optional[float] = Field(None, ge=0.0, le=1.0)
    road_type_vulnerability_factor: Optional[float] = Field(None, ge=0.0, le=1.0)
    road_vulnerability_factor: Optional[float] = Field(None, ge=0.0, le=1.0)
    congestion_factor: Optional[float] = Field(None, ge=0.0, le=1.0)
    nearby_flood_factor: Optional[float] = Field(None, ge=0.0, le=1.0)
    nearby_landslide_factor: Optional[float] = Field(None, ge=0.0, le=1.0)
    nearby_accident_factor: Optional[float] = Field(None, ge=0.0, le=1.0)
    nearby_flood_distance_km: Optional[float] = Field(None, ge=0.0)
    nearby_landslide_distance_km: Optional[float] = Field(None, ge=0.0)
    nearby_accident_distance_km: Optional[float] = Field(None, ge=0.0)
    nearby_flood_event_timestamp: Optional[datetime] = None
    nearby_landslide_event_timestamp: Optional[datetime] = None
    nearby_accident_event_timestamp: Optional[datetime] = None

    @field_validator(
        "latitude", "longitude", "lanes", "temperature", "vehicles_involved",
        "casualties", "rainfall_24h", "rainfall_3d", "rainfall_7d",
        "nearest_landslide_distance_km", "nearby_landslide_count", "nearest_river_distance_km",
        "flood_probability", "landslide_probability", "incident_risk", "rainfall_intensity_factor",
        "river_level_factor", "slope_factor", "terrain_susceptibility_factor", "flood_vulnerability_factor",
        "road_type_vulnerability_factor", "road_vulnerability_factor", "congestion_factor", "nearby_flood_factor",
        "nearby_landslide_factor", "nearby_accident_factor", "nearby_flood_distance_km", "nearby_landslide_distance_km",
        "nearby_accident_distance_km", mode="before"
    )
    @classmethod
    def reject_non_finite_numbers(cls, value):
        if value is None:
            return value
        parsed = float(value)
        if not math.isfinite(parsed):
            raise ValueError("numeric values must be finite")
        return value

class P3PredictionResponse(BaseModel):
    road_id: str
    timestamp: datetime
    risk_probability: float = Field(..., ge=0.0, le=1.0)
    operational_disruption_score: float = Field(..., ge=0.0, le=1.0)
    disruption_probability: Optional[float] = Field(None, ge=0.0, le=1.0)
    accessibility_score: float = Field(..., ge=0.0, le=100.0)
    model_version: str
    risk_target: str
    road_disruption_model_status: str = "insufficient_labels"
    score_components: Dict[str, Optional[float]]
    score_contributions: Dict[str, float]
    score_weights: Dict[str, float]
    available_components: List[str]
    weight_method: str
    weight_source: str
    weight_version: str
    disruption_method: Optional[str] = None
    disruption_category: Optional[str] = None
    evidence_completeness: Optional[float] = Field(None, ge=0.0, le=1.0)
    disruption_confidence: Optional[str] = None
    evidence_confidence: Optional[str] = None
    components: Optional[Dict[str, Optional[float]]] = None
    factors: Optional[Dict[str, Optional[float]]] = None
    evidence: Optional[Dict[str, bool]] = None
    explanation: Optional[Dict[str, Any]] = None
