from datetime import datetime
from typing import List, Literal
from pydantic import BaseModel, Field

Priority = Literal["CRITICAL", "HIGH", "NORMAL", "LOW"]

class RouteInfo(BaseModel):
    route_id: str
    estimated_travel_time_minutes: int = Field(ge=0)
    route_risk: float = Field(ge=0, le=1)

class ShipmentInput(BaseModel):
    shipment_id: str
    origin: str
    destination: str
    cargo_type: str
    quantity: float = Field(gt=0)
    unit: str
    priority: Priority
    requested_delivery: datetime
    route: RouteInfo

class ShipmentOutput(BaseModel):
    shipment_id: str
    priority: Priority
    route_id: str
    estimated_arrival: datetime
    shipment_risk: float
    status: Literal["PLANNED", "ON_ROUTE", "DELIVERED", "DELAYED"]

class ShortageInput(BaseModel):
    district_id: str
    district_name: str
    product_type: str
    current_inventory_units: float = Field(ge=0)
    average_daily_consumption: float = Field(gt=0)
    incoming_quantity_units: float = Field(ge=0)
    incoming_eta_days: float = Field(ge=0)
    road_risk: float = Field(ge=0, le=1)
    population: int = Field(gt=0)

class ShortageOutput(BaseModel):
    district_id: str
    product_type: str
    shortage_probability: float
    estimated_days_until_shortage: float
    risk_level: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    confidence: float
    model_version: str
    timestamp: datetime

class Warehouse(BaseModel):
    warehouse_id: str
    location: str
    available_units: float = Field(ge=0)

class TargetDistrict(BaseModel):
    district_id: str
    demand_units: float = Field(gt=0)
    shortage_probability: float = Field(ge=0, le=1)

class WarehouseOptimizationInput(BaseModel):
    product_type: str
    warehouses: List[Warehouse]
    target_districts: List[TargetDistrict]

class Recommendation(BaseModel):
    from_warehouse: str
    to_location: str
    product_type: str
    recommended_quantity: float
    reason: str

class WarehouseOptimizationOutput(BaseModel):
    recommendations: List[Recommendation]
    optimization_status: Literal["OPTIMAL", "FEASIBLE", "NO_FEASIBLE_ALLOCATION"]
