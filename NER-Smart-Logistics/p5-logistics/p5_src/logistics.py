import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict

import httpx

from .schemas import (
    InventoryItem,
    Recommendation,
    RouteInfo,
    ShipmentInput,
    ShipmentOutput,
    ShortageInput,
    ShortageOutput,
    Warehouse,
    WarehouseOptimizationInput,
    WarehouseOptimizationOutput,
    DemandInput,
    DemandOutput,
)


class P4RouteClient:
    """
    Client used by P5 to communicate with the P4 Risk-Aware Routing service.
    """

    def __init__(self):
        self.base_url = os.getenv(
            "P4_BASE_URL",
            "http://127.0.0.1:8001",
        )

    def optimize_route(
        self,
        origin: str,
        destination: str,
        cargo_type: str,
        priority: str,
    ) -> RouteInfo:
        """
        Request route information from P4.
        """

        payload = {
            "origin": origin,
            "destination": destination,
            "cargo_type": cargo_type,
            "priority": priority,
        }

        response = httpx.post(
            f"{self.base_url}/api/v1/routes/optimize",
            json=payload,
            timeout=30.0,
        )

        response.raise_for_status()

        data = response.json()

        return RouteInfo(
            route_id=data["route_id"],
            estimated_travel_time_minutes=data[
                "estimated_travel_time_minutes"
            ],
            route_risk=data["route_risk"],
            weather_risk=data.get("weather_risk"),
            flood_risk=data.get("flood_risk"),
            landslide_risk=data.get("landslide_risk"),
            imd_warning_risk=data.get("imd_warning_risk"),
            news_risk=data.get("news_risk"),
            safety_score=data.get("safety_score"),
            distance_km=data.get("distance_km"),
        )


class LogisticsService:
    """
    Core business logic for P5 - Logistics & Supply Chain.

    Responsibilities:
    - Shipment management
    - P4 route integration
    - Warehouse management
    - Inventory management
    - Inventory reservation
    - Warehouse optimization
    - Shortage prediction
    """

    def __init__(self):

        self.shipments: Dict[str, ShipmentOutput] = {}

        self.warehouses: Dict[str, Warehouse] = {}

        self.inventory: Dict[str, InventoryItem] = {}

        self.p4_client = P4RouteClient()

        self._load_warehouses()
        self._load_inventory()

    # ============================================================
    # WAREHOUSE MANAGEMENT
    # ============================================================

    def _load_warehouses(self):
        """
        Load warehouse master data from data/warehouses.json.
        """

        root_data = Path(__file__).resolve().parent.parent.parent / "data" / "p5_logistics" / "warehouses.json"
        local_data = Path(__file__).resolve().parent.parent / "data" / "warehouses.json"
        data_path = root_data if root_data.exists() else local_data

        if not data_path.exists():
            raise FileNotFoundError(
                f"Warehouse data file not found: {data_path}"
            )

        with open(data_path, "r", encoding="utf-8") as file:
            raw_data = json.load(file)

        items = raw_data if isinstance(raw_data, list) else raw_data.get("warehouses", [])
        for item in items:

            warehouse = Warehouse(**item)

            if warehouse.current_utilization > warehouse.storage_capacity:
                raise ValueError(
                    f"Warehouse {warehouse.warehouse_id} "
                    f"has utilization greater than capacity"
                )

            if warehouse.warehouse_id in self.warehouses:
                raise ValueError(
                    f"Duplicate warehouse ID: {warehouse.warehouse_id}"
                )

            self.warehouses[
                warehouse.warehouse_id
            ] = warehouse

    # ------------------------------------------------------------

    def get_warehouse_utilization(
        self,
        warehouse_id: str,
    ) -> float:
        """
        Calculate actual warehouse utilization from inventory.

        Utilization =
        available stock
        + reserved stock
        + in-transit stock
        """

        if warehouse_id not in self.warehouses:
            raise ValueError(
                f"Unknown warehouse: {warehouse_id}"
            )

        total = 0.0

        for item in self.inventory.values():

            if item.warehouse_id != warehouse_id:
                continue

            total += (
                item.quantity_available
                + item.quantity_reserved
                + item.quantity_in_transit
            )

        return total

    # ------------------------------------------------------------

    def get_available_capacity(
        self,
        warehouse_id: str,
    ) -> float:
        """
        Return remaining warehouse storage capacity.
        """

        warehouse = self.warehouses.get(
            warehouse_id
        )

        if warehouse is None:
            raise ValueError(
                f"Unknown warehouse: {warehouse_id}"
            )

        utilization = self.get_warehouse_utilization(
            warehouse_id
        )

        return max(
            0.0,
            warehouse.storage_capacity - utilization,
        )

    # ============================================================
    # INVENTORY MANAGEMENT
    # ============================================================

    def _load_inventory(self):
        """
        Load inventory data from data/inventory.json.
        """

        root_data = Path(__file__).resolve().parent.parent.parent / "data" / "p5_logistics" / "inventory.json"
        local_data = Path(__file__).resolve().parent.parent / "data" / "inventory.json"
        data_path = root_data if root_data.exists() else local_data

        if not data_path.exists():
            raise FileNotFoundError(
                f"Inventory data file not found: {data_path}"
            )

        with open(data_path, "r", encoding="utf-8") as file:
            data = json.load(file)

        for item in data:

            inventory_item = InventoryItem(**item)

            if inventory_item.warehouse_id not in self.warehouses:
                raise ValueError(
                    f"Inventory {inventory_item.inventory_id} "
                    f"references unknown warehouse "
                    f"{inventory_item.warehouse_id}"
                )

            if inventory_item.inventory_id in self.inventory:
                raise ValueError(
                    f"Duplicate inventory ID: "
                    f"{inventory_item.inventory_id}"
                )

            self.inventory[
                inventory_item.inventory_id
            ] = inventory_item

    # ------------------------------------------------------------

    def get_inventory_for_product(
        self,
        product_type: str,
    ):
        """
        Return active inventory entries for a product.
        """

        result = []

        for item in self.inventory.values():

            warehouse = self.warehouses.get(
                item.warehouse_id
            )

            if warehouse is None:
                continue

            if warehouse.status != "ACTIVE":
                continue

            if (
                item.product_type.upper()
                != product_type.upper()
            ):
                continue

            if item.quantity_available <= 0:
                continue

            result.append(item)

        return result

    # ------------------------------------------------------------

    def get_available_inventory(
        self,
        warehouse_id: str,
        product_type: str,
    ) -> float:
        """
        Return total available quantity of a product
        in a warehouse.
        """

        total = 0.0

        for item in self.inventory.values():

            if item.warehouse_id != warehouse_id:
                continue

            if (
                item.product_type.upper()
                != product_type.upper()
            ):
                continue

            total += item.quantity_available

        return total

    # ------------------------------------------------------------

    def reserve_inventory(
        self,
        warehouse_id: str,
        product_type: str,
        quantity: float,
    ) -> bool:
        """
        Reserve inventory for a shipment.

        Available stock decreases.
        Reserved stock increases.
        """

        if quantity <= 0:
            return False

        remaining = quantity

        matching_items = [
            item
            for item in self.inventory.values()
            if (
                item.warehouse_id == warehouse_id
                and item.product_type.upper()
                == product_type.upper()
                and item.quantity_available > 0
            )
        ]

        for item in matching_items:

            if remaining <= 0:
                break

            reserve_qty = min(
                item.quantity_available,
                remaining,
            )

            item.quantity_available -= reserve_qty
            item.quantity_reserved += reserve_qty

            remaining -= reserve_qty

            item.last_updated = datetime.now(
                timezone.utc
            )

        return remaining <= 0

    # ------------------------------------------------------------

    def release_reserved_inventory(
        self,
        warehouse_id: str,
        product_type: str,
        quantity: float,
    ) -> bool:
        """
        Release previously reserved inventory.
        """

        if quantity <= 0:
            return False

        remaining = quantity

        matching_items = [
            item
            for item in self.inventory.values()
            if (
                item.warehouse_id == warehouse_id
                and item.product_type.upper()
                == product_type.upper()
                and item.quantity_reserved > 0
            )
        ]

        for item in matching_items:

            if remaining <= 0:
                break

            release_qty = min(
                item.quantity_reserved,
                remaining,
            )

            item.quantity_reserved -= release_qty
            item.quantity_available += release_qty

            remaining -= release_qty

            item.last_updated = datetime.now(
                timezone.utc
            )

        return remaining <= 0

    # ============================================================
    # SHIPMENT MANAGEMENT
    # ============================================================

    def create_shipment(
        self,
        payload: ShipmentInput,
    ) -> ShipmentOutput:
        """
        Create a shipment.

        Flow:

        Frontend
            ↓
        P5
            ↓
        P4 route optimization
            ↓
        Inventory check
            ↓
        Inventory reservation
            ↓
        Shipment creation
        """

        if payload.shipment_id in self.shipments:
            raise ValueError(
                f"Shipment already exists: "
                f"{payload.shipment_id}"
            )

        # --------------------------------------------------------
        # Get route from P4
        # --------------------------------------------------------

        route = self.p4_client.optimize_route(
            origin=payload.origin,
            destination=payload.destination,
            cargo_type=payload.cargo_type,
            priority=payload.priority,
        )

        # --------------------------------------------------------
        # Find inventory
        # --------------------------------------------------------

        inventory_items = self.get_inventory_for_product(
            payload.cargo_type
        )

        if not inventory_items:
            raise ValueError(
                f"No available inventory found for "
                f"{payload.cargo_type}"
            )

        # --------------------------------------------------------
        # Find warehouse with sufficient inventory
        # --------------------------------------------------------

        selected_warehouse = None

        for item in inventory_items:

            available = self.get_available_inventory(
                item.warehouse_id,
                payload.cargo_type,
            )

            if available >= payload.quantity:
                selected_warehouse = item.warehouse_id
                break

        if selected_warehouse is None:
            raise ValueError(
                f"Insufficient inventory for "
                f"{payload.cargo_type}"
            )

        # --------------------------------------------------------
        # Reserve inventory
        # --------------------------------------------------------

        reserved = self.reserve_inventory(
            warehouse_id=selected_warehouse,
            product_type=payload.cargo_type,
            quantity=payload.quantity,
        )

        if not reserved:
            raise ValueError(
                "Inventory reservation failed"
            )

        # --------------------------------------------------------
        # Shipment risk
        # --------------------------------------------------------

        shipment_risk = round(
            route.route_risk,
            4,
        )

        # --------------------------------------------------------
        # Estimated arrival
        # --------------------------------------------------------

        estimated_arrival = (
            datetime.now(timezone.utc)
            + timedelta(
                minutes=route.estimated_travel_time_minutes
            )
        )

        # --------------------------------------------------------
        # Create shipment
        # --------------------------------------------------------

        shipment = ShipmentOutput(
            shipment_id=payload.shipment_id,
            origin=payload.origin,
            destination=payload.destination,
            cargo_type=payload.cargo_type,
            quantity=payload.quantity,
            unit=payload.unit,
            priority=payload.priority,

            route_id=route.route_id,

            estimated_travel_time_minutes=(
                route.estimated_travel_time_minutes
            ),

            distance_km=route.distance_km,

            estimated_arrival=estimated_arrival,

            shipment_risk=shipment_risk,

            route_risk=route.route_risk,
            weather_risk=route.weather_risk,
            flood_risk=route.flood_risk,
            landslide_risk=route.landslide_risk,
            imd_warning_risk=route.imd_warning_risk,
            news_risk=route.news_risk,
            safety_score=route.safety_score,

            status="PLANNED",
        )

        self.shipments[
            payload.shipment_id
        ] = shipment

        return shipment

    def optimize_warehouses(
        self,
        data: WarehouseOptimizationInput,
    ) -> WarehouseOptimizationOutput:
        inventory_items = self.get_inventory_for_product(data.product_type)
        remaining_inventory = {
            item.inventory_id: item.quantity_available
            for item in inventory_items
        }
        recommendations = []

        for target in sorted(
            data.target_districts,
            key=lambda item: item.shortage_probability,
            reverse=True,
        ):
            remaining_demand = target.demand_units
            for item in inventory_items:
                if remaining_demand <= 0:
                    break

                warehouse = self.warehouses.get(item.warehouse_id)
                available = remaining_inventory[item.inventory_id]
                if not warehouse or warehouse.status != "ACTIVE" or available <= 0:
                    continue

                quantity = min(available, remaining_demand)
                remaining_inventory[item.inventory_id] -= quantity
                remaining_demand -= quantity
                reason = (
                    "CRITICAL_SHORTAGE_RISK"
                    if target.shortage_probability >= 0.85
                    else "HIGH_SHORTAGE_RISK"
                    if target.shortage_probability >= 0.65
                    else "DEMAND_REBALANCING"
                )
                recommendations.append(
                    Recommendation(
                        from_warehouse=item.warehouse_id,
                        to_location=target.district_id,
                        product_type=data.product_type,
                        recommended_quantity=round(quantity, 2),
                        reason=reason,
                    )
                )

        total_demand = sum(
            target.demand_units for target in data.target_districts
        )
        total_allocated = sum(
            item.recommended_quantity for item in recommendations
        )
        status = (
            "OPTIMAL"
            if total_allocated >= total_demand
            else "FEASIBLE"
            if total_allocated > 0
            else "NO_FEASIBLE_ALLOCATION"
        )
        return WarehouseOptimizationOutput(
            recommendations=recommendations,
            optimization_status=status,
        )

    def predict_shortage(
        self,
        payload: ShortageInput,
    ) -> ShortageOutput:
        daily_consumption = payload.average_daily_consumption
        current_days = payload.current_inventory_units / daily_consumption
        incoming = (
            payload.incoming_quantity_units
            if payload.incoming_eta_days <= current_days
            else 0
        )
        projected_days = (
            payload.current_inventory_units + incoming
        ) / daily_consumption

        if projected_days <= 1:
            probability = 0.95
        elif projected_days <= 3:
            probability = 0.85
        elif projected_days <= 7:
            probability = 0.65
        elif projected_days <= 14:
            probability = 0.35
        else:
            probability = 0.10

        route_id = None
        route_risk = None
        try:
            route = self.p4_client.optimize_route(
                origin=payload.origin,
                destination=payload.district_name,
                cargo_type=payload.product_type,
                priority=payload.priority,
            )
            route_id = route.route_id
            route_risk = route.route_risk
            probability = min(1.0, probability + 0.15 * route_risk)
        except Exception:
            pass

        probability = min(1.0, max(0.0, probability))
        risk_level = (
            "CRITICAL"
            if probability >= 0.85
            else "HIGH"
            if probability >= 0.65
            else "MEDIUM"
            if probability >= 0.35
            else "LOW"
        )
        confidence = 0.65 if route_id is not None else 0.60
        return ShortageOutput(
            district_id=payload.district_id,
            district_name=payload.district_name,
            product_type=payload.product_type,
            shortage_probability=round(probability, 4),
            estimated_days_until_shortage=round(projected_days, 2),
            risk_level=risk_level,
            confidence=confidence,
            model_version="shortage_baseline_route_v1",
            timestamp=datetime.now(timezone.utc),
            route_id=route_id,
            road_risk=route_risk,
        )

    # ============================================================
    # SHORTAGE PREDICTION
    # ============================================================

# ============================================================
# SHORTAGE PREDICTION
# ============================================================

def predict_shortage(
    self,
    payload: ShortageInput,
) -> ShortageOutput:
    """
    Demand-aware shortage prediction.

    Pipeline:

        Historical demand
              ↓
        Demand forecast
              ↓
        Inventory coverage
              ↓
        Base shortage probability
              ↓
        P4 route-risk adjustment
              ↓
        Final shortage probability
    """

    current_inventory = payload.current_inventory_units
    incoming_quantity = payload.incoming_quantity_units
    eta_days = payload.incoming_eta_days

    # --------------------------------------------------------
    # 1. Determine daily demand
    # --------------------------------------------------------

    if (
        payload.historical_daily_demand
        and len(payload.historical_daily_demand) >= 3
    ):
        demand_input = DemandInput(
            district_id=payload.district_id,
            district_name=payload.district_name,
            product_type=payload.product_type,
            historical_daily_demand=payload.historical_daily_demand,
            forecast_days=max(7, int(eta_days) + 7),
        )

        demand_forecast = self.predict_demand(
            demand_input
        )

        daily_consumption = (
            demand_forecast.predicted_daily_demand
        )

    else:
        # Backward-compatible fallback
        daily_consumption = (
            payload.average_daily_consumption
        )

    daily_consumption = max(
        daily_consumption,
        0.01,
    )

    # --------------------------------------------------------
    # 2. Current inventory coverage
    # --------------------------------------------------------

    current_days = (
        current_inventory / daily_consumption
    )

    # --------------------------------------------------------
    # 3. Incoming inventory
    #
    # If the shipment arrives before current stock is
    # exhausted, include it in projected inventory.
    # --------------------------------------------------------

    incoming_before_shortage = (
        incoming_quantity
        if eta_days <= current_days
        else 0.0
    )

    effective_inventory = (
        current_inventory
        + incoming_before_shortage
    )

    days_until_shortage = (
        effective_inventory / daily_consumption
    )

    # --------------------------------------------------------
    # 4. Base shortage probability
    # --------------------------------------------------------

    if days_until_shortage <= 1:
        probability = 0.95

    elif days_until_shortage <= 3:
        probability = 0.85

    elif days_until_shortage <= 7:
        probability = 0.65

    elif days_until_shortage <= 14:
        probability = 0.35

    else:
        probability = 0.10

    # --------------------------------------------------------
    # 5. Population adjustment
    # --------------------------------------------------------

    if payload.population >= 1_000_000:
        probability += 0.03

    elif payload.population >= 500_000:
        probability += 0.02

    # --------------------------------------------------------
    # 6. P4 route-risk adjustment
    #
    # A high-risk route makes incoming relief less reliable.
    # Therefore shortage probability increases slightly.
    # --------------------------------------------------------

    route_id = None
    route_risk = None
    weather_risk = None
    flood_risk = None
    landslide_risk = None
    imd_warning_risk = None
    news_risk = None

    try:
        route = self.p4_client.optimize_route(
            origin=payload.origin,
            destination=payload.district_name,
            cargo_type=payload.product_type,
            priority=payload.priority,
        )

        route_id = route.route_id
        route_risk = route.route_risk
        weather_risk = route.weather_risk
        flood_risk = route.flood_risk
        landslide_risk = route.landslide_risk
        imd_warning_risk = route.imd_warning_risk
        news_risk = route.news_risk

        # Maximum route-risk contribution = +0.15
        route_adjustment = 0.15 * route_risk

        probability += route_adjustment

    except Exception:
        # P4 failure should not stop shortage prediction.
        pass

    probability = min(
        1.0,
        max(0.0, probability),
    )

    # --------------------------------------------------------
    # 7. Risk level
    # --------------------------------------------------------

    if probability >= 0.85:
        risk_level = "CRITICAL"

    elif probability >= 0.65:
        risk_level = "HIGH"

    elif probability >= 0.35:
        risk_level = "MEDIUM"

    else:
        risk_level = "LOW"

    # --------------------------------------------------------
    # 8. Confidence
    #
    # More historical demand observations = more confidence.
    # Route availability gives a small additional confidence
    # boost because P4 intelligence is available.
    # --------------------------------------------------------

    if payload.historical_daily_demand:
        history_confidence = min(
            0.20,
            len(payload.historical_daily_demand) / 100
        )
    else:
        history_confidence = 0.0

    route_confidence = (
        0.05
        if route_id is not None
        else 0.0
    )

    confidence = min(
        0.95,
        0.60
        + history_confidence
        + route_confidence,
    )

    # --------------------------------------------------------
    # 9. Return
    # --------------------------------------------------------

    model_version = (
        "shortage_demand_route_v1"
        if payload.historical_daily_demand
        else "shortage_baseline_route_v1"
    )

    return ShortageOutput(
        district_id=payload.district_id,
        district_name=payload.district_name,
        product_type=payload.product_type,

        shortage_probability=round(
            probability,
            4,
        ),

        estimated_days_until_shortage=round(
            days_until_shortage,
            2,
        ),

        risk_level=risk_level,

        confidence=round(
            confidence,
            2,
        ),

        model_version=model_version,

        timestamp=datetime.now(
            timezone.utc
        ),

        route_id=route_id,
        road_risk=route_risk,
        weather_risk=weather_risk,
        flood_risk=flood_risk,
        landslide_risk=landslide_risk,
        imd_warning_risk=imd_warning_risk,
        news_risk=news_risk,
    )


    # ============================================================
    # ROUTE-AWARE WAREHOUSE OPTIMIZATION
    # ============================================================

    def _get_route_score(
        self,
        warehouse: Warehouse,
        target_district: str,
        product_type: str,
    ) -> tuple:
        """
        Get route information from P4 and calculate a
        comparable warehouse-selection score.

        Lower score = better warehouse.

        Weighting:
        - 60% route risk
        - 25% travel time
        - 15% distance
        """

        route = self.p4_client.optimize_route(
            origin=warehouse.district,
            destination=target_district,
            cargo_type=product_type,
            priority="HIGH",
        )

        # --------------------------------------------------------
        # Risk score
        # --------------------------------------------------------

        risk_score = route.route_risk

        # --------------------------------------------------------
        # Travel-time normalization
        # --------------------------------------------------------

        time_score = min(
            route.estimated_travel_time_minutes / 600.0,
            1.0,
        )

        # --------------------------------------------------------
        # Distance normalization
        # --------------------------------------------------------

        distance_score = 0.0

        if route.distance_km is not None:
            distance_score = min(
                route.distance_km / 500.0,
                1.0,
            )

        # --------------------------------------------------------
        # Final score
        # --------------------------------------------------------

        score = (
            0.60 * risk_score
            + 0.25 * time_score
            + 0.15 * distance_score
        )

        return score, route

    # ------------------------------------------------------------

    def optimize_warehouses(
        self,
        data: WarehouseOptimizationInput,
    ) -> WarehouseOptimizationOutput:
        """
        Route-aware warehouse optimization.

        For each target district:

        1. Find warehouses containing the requested product.
        2. Ask P4 for a route from each candidate warehouse.
        3. Calculate a route score.
        4. Rank candidate warehouses.
        5. Allocate inventory from the best warehouse(s).

        Inventory is NOT permanently changed here.
        Actual reservation occurs when a shipment is created.
        """

        # --------------------------------------------------------
        # Get inventory for requested product
        # --------------------------------------------------------

        inventory_items = self.get_inventory_for_product(
            data.product_type
        )

        if not inventory_items:
            return WarehouseOptimizationOutput(
                recommendations=[],
                optimization_status=(
                    "NO_FEASIBLE_ALLOCATION"
                ),
            )

        # --------------------------------------------------------
        # Highest shortage risk first
        # --------------------------------------------------------

        targets = sorted(
            data.target_districts,
            key=lambda x: x.shortage_probability,
            reverse=True,
        )

        # --------------------------------------------------------
        # Temporary inventory state
        # --------------------------------------------------------

        remaining_inventory = {
            item.inventory_id: item.quantity_available
            for item in inventory_items
        }

        recommendations = []

        # --------------------------------------------------------
        # Process every target district
        # --------------------------------------------------------

        for target in targets:

            need = target.demand_units

            if need <= 0:
                continue

            # ----------------------------------------------------
            # Build candidate warehouse list
            # ----------------------------------------------------

            candidates = []

            for item in inventory_items:

                available = remaining_inventory[
                    item.inventory_id
                ]

                if available <= 0:
                    continue

                warehouse = self.warehouses.get(
                    item.warehouse_id
                )

                if warehouse is None:
                    continue

                if warehouse.status != "ACTIVE":
                    continue

                # ------------------------------------------------
                # P4 route evaluation
                #
                # IMPORTANT:
                # district_name is sent to P4, not district_id.
                # ------------------------------------------------

                try:
                    route_score, route = (
                        self._get_route_score(
                            warehouse=warehouse,
                            target_district=(
                                target.district_name
                            ),
                            product_type=data.product_type,
                        )
                    )

                except Exception:
                    # One failed P4 route should not prevent
                    # other warehouses from being evaluated.
                    continue

                candidates.append(
                    {
                        "inventory": item,
                        "warehouse": warehouse,
                        "route": route,
                        "score": route_score,
                        "available": available,
                    }
                )

            # ----------------------------------------------------
            # No feasible warehouse
            # ----------------------------------------------------

            if not candidates:
                continue

            # ----------------------------------------------------
            # Safest/best route first
            # ----------------------------------------------------

            candidates.sort(
                key=lambda x: x["score"]
            )

            # ----------------------------------------------------
            # Allocate from ranked warehouses
            # ----------------------------------------------------

            for candidate in candidates:

                if need <= 0:
                    break

                item = candidate["inventory"]

                available = remaining_inventory[
                    item.inventory_id
                ]

                if available <= 0:
                    continue

                quantity = min(
                    available,
                    need,
                )

                if quantity <= 0:
                    continue

                # Temporary allocation
                remaining_inventory[
                    item.inventory_id
                ] -= quantity

                need -= quantity

                # ------------------------------------------------
                # Recommendation reason
                # ------------------------------------------------

                if target.shortage_probability >= 0.85:
                    reason = "CRITICAL_SHORTAGE_RISK"

                elif target.shortage_probability >= 0.65:
                    reason = "HIGH_SHORTAGE_RISK"

                else:
                    reason = "DEMAND_REBALANCING"

                # ------------------------------------------------
                # Recommendation
                # ------------------------------------------------

                recommendations.append(
                    Recommendation(
                        from_warehouse=item.warehouse_id,
                        to_location=target.district_id,
                        product_type=data.product_type,
                        recommended_quantity=round(
                            quantity,
                            2,
                        ),
                        reason=reason,
                    )
                )

        # --------------------------------------------------------
        # Calculate allocation
        # --------------------------------------------------------

        total_demand = sum(
            target.demand_units
            for target in data.target_districts
        )

        total_allocated = sum(
            recommendation.recommended_quantity
            for recommendation in recommendations
        )

        # --------------------------------------------------------
        # Optimization status
        # --------------------------------------------------------

        if total_allocated >= total_demand:
            optimization_status = "OPTIMAL"

        elif total_allocated > 0:
            optimization_status = "FEASIBLE"

        else:
            optimization_status = (
                "NO_FEASIBLE_ALLOCATION"
            )

        return WarehouseOptimizationOutput(
            recommendations=recommendations,
            optimization_status=optimization_status,
        )

# ============================================================
# DEMAND PREDICTION
# ============================================================

def predict_demand(
    self,
    payload: DemandInput
) -> DemandOutput:
    """
    Predict future demand using a weighted moving-average
    baseline.

    Recent observations receive more importance than older
    observations.
    """

    history = payload.historical_daily_demand

    if len(history) < 3:
        raise ValueError(
            "At least 3 historical demand values are required"
        )

    # Use the most recent 7 observations
    recent = history[-7:]

    # Give more weight to recent demand
    weights = list(range(1, len(recent) + 1))

    weighted_sum = sum(
        demand * weight
        for demand, weight in zip(recent, weights)
    )

    total_weight = sum(weights)

    baseline = weighted_sum / total_weight

    # Simple trend detection
    midpoint = len(recent) // 2

    first_half = recent[:midpoint]
    second_half = recent[midpoint:]

    first_avg = sum(first_half) / len(first_half)
    second_avg = sum(second_half) / len(second_half)

    trend = second_avg - first_avg

    # Limit trend influence so abnormal values do not
    # create unrealistic forecasts.
    max_trend = baseline * 0.25

    trend = max(
        -max_trend,
        min(trend, max_trend)
    )

    predicted_daily_demand = max(
        0.0,
        baseline + trend
    )

    predicted_total_demand = (
        predicted_daily_demand
        * payload.forecast_days
    )

    # Confidence increases with more historical observations.
    confidence = min(
        0.95,
        0.60 + (len(history) / 100)
    )

    return DemandOutput(
        district_id=payload.district_id,
        district_name=payload.district_name,
        product_type=payload.product_type,
        forecast_days=payload.forecast_days,
        predicted_daily_demand=round(
            predicted_daily_demand,
            2
        ),
        predicted_total_demand=round(
            predicted_total_demand,
            2
        ),
        confidence=round(confidence, 2),
        model_version="demand_weighted_moving_average_v1",
        timestamp=datetime.now(timezone.utc),
    )



