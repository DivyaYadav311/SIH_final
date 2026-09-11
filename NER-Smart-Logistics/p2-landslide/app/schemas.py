from typing import Any, Literal, Optional
from pydantic import BaseModel, Field, ConfigDict


LandCover = Literal[
    "forest", "cropland", "grassland", "barren",
    "urban", "snow_ice", "shrubland", "wetland"
]


class LandslideRequest(BaseModel):
    """Only coordinates are required. All other features are fetched live."""
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "location_id": "LOC_001",
            "latitude": 27.5840,
            "longitude": 91.8730
        }
    })

    location_id: Optional[str] = None
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)


class LiveFeatures(BaseModel):
    rainfall_1h_mm: float
    rainfall_6h_mm: float
    rainfall_24h_mm: float
    rainfall_7d_mm: float
    temperature_c: float
    humidity_percent: float
    elevation_m: float
    slope_degree: float
    aspect_degree: float
    land_cover: LandCover
    historical_landslide_count: int


class LandslidePrediction(BaseModel):
    location_id: str
    latitude: float
    longitude: float
    landslide_probability: float
    risk_level: Literal["LOW", "MODERATE", "HIGH", "CRITICAL"]
    confidence: float
    model_version: str
    timestamp: str
    live_features: LiveFeatures
    data_sources: dict[str, str]
    source_status: dict[str, str]
    satellite_observation: dict[str, Any]
