from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


# ============================================================
# COMMON
# ============================================================

Priority = Literal[
    "CRITICAL",
    "HIGH",
    "NORMAL",
    "LOW",
]


# ============================================================
# ROUTE
# ============================================================

class RouteInfo(BaseModel):
    route_id: str

    estimated_travel_time_minutes: float = Field(
        ge=0
    )

    route_risk: float = Field(
        ge=0,
        le=1
    )

    weather_risk: Optional[float] = Field(
        default=None,
        ge=0,
        le=1
    )

    flood_risk: Optional[float] = Field(
        default=None,
        ge=0,
        le=1
    )

    landslide_risk: Optional[float] = Field(
        default=None,
        ge=0,
        le=1
    )

    imd_warning_risk: Optional[float] = Field(
        default=None,
        ge=0,
        le=1
    )

    news_risk: Optional[float] = Field(
        default=None,
        ge=0,
        le=1
    )

    safety_score: Optional[float] = Field(
        default=None,
        ge=0,
        le=100
    )

    distance_km: Optional[float] = Field(
        default=None,
        ge=0
    )


# ============================================================
# SHIPMENTS
# ============================================================

class ShipmentInput(BaseModel):
    shipment_id: str

    origin: str
    destination: str

    cargo_type: str

    quantity: float = Field(
        gt=0
    )

    unit: str

    priority: Priority

    requested_delivery: datetime

    # Optional for backward compatibility.
    # P5 obtains route information from P4.
    route: Optional[RouteInfo] = None


class ShipmentOutput(BaseModel):
    shipment_id: str

    origin: str
    destination: str

    cargo_type: str

    quantity: float

    unit: str

    priority: Priority

    route_id: str

    estimated_travel_time_minutes: float

    distance_km: Optional[float] = None

    estimated_arrival: datetime

    shipment_risk: float

    route_risk: float

    weather_risk: Optional[float] = None
    flood_risk: Optional[float] = None
    landslide_risk: Optional[float] = None
    imd_warning_risk: Optional[float] = None
    news_risk: Optional[float] = None

    safety_score: Optional[float] = None

    status: Literal[
        "PLANNED",
        "ON_ROUTE",
        "DELIVERED",
        "DELAYED",
    ]


# ============================================================
# SHORTAGE PREDICTION
# ============================================================

class ShortageInput(BaseModel):
    district_id: str

    district_name: str

    # Location from which P5 requests route information
    # from P4.
    origin: str

    product_type: str

    priority: Priority

    # Current available inventory in the target district.
    current_inventory_units: float = Field(
        ge=0
    )

    # Backward-compatible fallback.
    # Used when historical demand is not supplied.
    average_daily_consumption: float = Field(
        gt=0
    )

    # Historical demand observations.
    # When supplied, P5 uses the demand forecasting layer.
    historical_daily_demand: Optional[List[float]] = None

    # Expected incoming relief stock.
    incoming_quantity_units: float = Field(
        ge=0
    )

    incoming_eta_days: float = Field(
        ge=0
    )

    population: int = Field(
        gt=0
    )


class ShortageOutput(BaseModel):
    district_id: str

    district_name: str

    product_type: str

    shortage_probability: float

    estimated_days_until_shortage: float

    risk_level: Literal[
        "LOW",
        "MEDIUM",
        "HIGH",
        "CRITICAL",
    ]

    confidence: float

    model_version: str

    timestamp: datetime

    # P4 route intelligence
    route_id: Optional[str] = None

    road_risk: Optional[float] = None

    weather_risk: Optional[float] = None

    flood_risk: Optional[float] = None

    landslide_risk: Optional[float] = None

    imd_warning_risk: Optional[float] = None

    news_risk: Optional[float] = None


# ============================================================
# WAREHOUSE
# ============================================================

class Warehouse(BaseModel):
    warehouse_id: str

    name: str

    state: str
    district: str

    latitude: float = Field(
        ge=-90,
        le=90
    )

    longitude: float = Field(
        ge=-180,
        le=180
    )

    storage_capacity: float = Field(
        gt=0
    )

    current_utilization: float = Field(
        ge=0
    )

    status: Literal[
        "ACTIVE",
        "INACTIVE",
        "DAMAGED",
    ] = "ACTIVE"

    last_updated: Optional[datetime] = None

    @property
    def available_capacity(self) -> float:
        return max(
            0,
            self.storage_capacity
            - self.current_utilization,
        )


class WarehouseOutput(Warehouse):
    available_capacity: float


# ============================================================
# INVENTORY
# ============================================================

class InventoryItem(BaseModel):
    inventory_id: str

    warehouse_id: str

    product_type: str

    quantity_available: float = Field(
        ge=0
    )

    quantity_reserved: float = Field(
        ge=0
    )

    quantity_in_transit: float = Field(
        ge=0
    )

    last_updated: Optional[datetime] = None


# ============================================================
# DEMAND PREDICTION
# ============================================================

class DemandInput(BaseModel):
    district_id: str

    district_name: str

    product_type: str

    # Historical daily demand observations.
    historical_daily_demand: List[float] = Field(
        min_length=3
    )

    # Number of days to forecast.
    forecast_days: int = Field(
        default=7,
        gt=0,
        le=30
    )


class DemandOutput(BaseModel):
    district_id: str

    district_name: str

    product_type: str

    forecast_days: int

    predicted_daily_demand: float

    predicted_total_demand: float

    confidence: float

    model_version: str

    timestamp: datetime


# ============================================================
# WAREHOUSE OPTIMIZATION
# ============================================================

class TargetDistrict(BaseModel):
    district_id: str

    district_name: str = ""

    demand_units: float = Field(
        gt=0
    )

    shortage_probability: float = Field(
        ge=0,
        le=1
    )


class WarehouseOptimizationInput(BaseModel):
    product_type: str

    target_districts: List[TargetDistrict]


class Recommendation(BaseModel):
    from_warehouse: str

    to_location: str

    product_type: str

    recommended_quantity: float

    reason: str


class WarehouseOptimizationOutput(BaseModel):
    recommendations: List[Recommendation]

    optimization_status: Literal[
        "OPTIMAL",
        "FEASIBLE",
        "NO_FEASIBLE_ALLOCATION",
    ]

