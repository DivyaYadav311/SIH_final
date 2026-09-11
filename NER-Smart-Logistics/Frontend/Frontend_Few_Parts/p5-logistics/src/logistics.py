from datetime import timedelta, datetime, timezone
from typing import Dict, Any
from .schemas import *

PRIORITY_RISK = {"CRITICAL": 0.05, "HIGH": 0.10, "NORMAL": 0.15, "LOW": 0.20}

class LogisticsService:
    def __init__(self):
        self.shipments: Dict[str, ShipmentOutput] = {}

    def create_shipment(self, data: ShipmentInput) -> ShipmentOutput:
        route = data.route
        # Baseline shipment risk. P4 can replace route_risk with its live output during integration.
        risk = min(1.0, 0.75 * route.route_risk + 0.25 * PRIORITY_RISK[data.priority])
        eta = data.requested_delivery - timedelta(minutes=0)
        # requested_delivery is a deadline; arrival is computed from a route start at current UTC time.
        eta = datetime.now(timezone.utc) + timedelta(minutes=route.estimated_travel_time_minutes)
        status = "DELAYED" if eta > data.requested_delivery else "ON_ROUTE"
        result = ShipmentOutput(
            shipment_id=data.shipment_id,
            priority=data.priority,
            route_id=route.route_id,
            estimated_arrival=eta,
            shipment_risk=round(risk, 4),
            status=status,
        )
        self.shipments[data.shipment_id] = result
        return result

    def predict_shortage(self, data: ShortageInput) -> ShortageOutput:
        # Explainable MVP baseline. Replace with trained XGBoost model without changing API contract.
        daily = max(data.average_daily_consumption, 1e-6)
        days_now = data.current_inventory_units / daily
        effective_days = (data.current_inventory_units + data.incoming_quantity_units) / daily
        arrival_gap = max(0.0, data.incoming_eta_days - days_now)
        # Logistic baseline: high road risk + incoming supply arriving after current stock
        # is exhausted should produce a sharply higher shortage probability.
        inventory_pressure = min(1.0, 1.0 / max(days_now, 0.25))
        z = -2.0 + 2.8 * data.road_risk + 1.5 * arrival_gap + 1.2 * inventory_pressure
        probability = 1.0 / (1.0 + pow(2.718281828, -z))
        probability = min(0.99, max(0.01, probability))
        risk_level = "CRITICAL" if probability >= 0.85 else "HIGH" if probability >= 0.65 else "MEDIUM" if probability >= 0.35 else "LOW"
        confidence = round(min(0.95, 0.65 + 0.25 * min(1.0, days_now / 7.0)), 2)
        days_until = max(0.0, days_now)
        return ShortageOutput(
            district_id=data.district_id,
            product_type=data.product_type,
            shortage_probability=round(probability, 4),
            estimated_days_until_shortage=round(days_until, 2),
            risk_level=risk_level,
            confidence=confidence,
            model_version="shortage_baseline_v1",
            timestamp=datetime.now(timezone.utc),
        )

    def optimize_warehouses(self, data: WarehouseOptimizationInput) -> WarehouseOptimizationOutput:
        # Greedy allocation: highest shortage risk first, then consume nearest-listed warehouse capacity.
        warehouses = [w.model_copy() for w in data.warehouses]
        targets = sorted(data.target_districts, key=lambda x: x.shortage_probability, reverse=True)
        recs = []
        for target in targets:
            need = target.demand_units
            for wh in warehouses:
                if need <= 0:
                    break
                qty = min(wh.available_units, need)
                if qty <= 0:
                    continue
                wh.available_units -= qty
                need -= qty
                recs.append(Recommendation(
                    from_warehouse=wh.warehouse_id,
                    to_location=target.district_id,
                    product_type=data.product_type,
                    recommended_quantity=round(qty, 2),
                    reason="CRITICAL_SHORTAGE_RISK" if target.shortage_probability >= 0.85 else "HIGH_SHORTAGE_RISK" if target.shortage_probability >= 0.65 else "DEMAND_REBALANCING",
                ))
        total_demand = sum(t.demand_units for t in data.target_districts)
        total_allocated = sum(r.recommended_quantity for r in recs)
        status = "OPTIMAL" if total_allocated >= total_demand else "FEASIBLE" if total_allocated > 0 else "NO_FEASIBLE_ALLOCATION"
        return WarehouseOptimizationOutput(recommendations=recs, optimization_status=status)
