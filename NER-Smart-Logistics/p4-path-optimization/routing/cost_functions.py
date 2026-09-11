"""Cost model for physically travelable OSM road edges."""
from __future__ import annotations
from p4_src.config import PRIORITY_RISK_MULTIPLIER, WEIGHT_DISTANCE, WEIGHT_RISK, WEIGHT_TRAVEL_TIME


def compute_edge_cost(edge_data: dict, priority: str = "medium", avoid_high_risk: bool = True,
                      vehicle_weight_tons: float = 10.0, transport_mode: str = "road",
                      goal: str = "safest") -> float:
    edge_mode = edge_data.get("mode", "road")
    if transport_mode == "road" and edge_mode != "road":
        return 1e12
    if transport_mode not in {"road", "multimodal"}:
        return 1e12
    if vehicle_weight_tons > float(edge_data.get("max_weight_tons", 1000.0)):
        return 1e12

    # Strictly prohibit non-drivable paths (tracks, footways, walking trails, service ways)
    # Commercial transit and emergency logistics CANNOT travel on paths or wilderness tracks.
    hw = str(edge_data.get("highway", "primary")).lower()
    NON_DRIVABLE = {
        "track", "path", "footway", "pedestrian", "service", "living_street",
        "steps", "cycleway", "bridleway", "corridor", "abandoned", "proposed",
        "construction", "escape", "raceway", "bus_guideway", "footpath"
    }
    if hw in NON_DRIVABLE or edge_data.get("access") in {"no", "private"}:
        return 1e12

    disruption = float(edge_data.get("disruption_probability", 0.0))
    if avoid_high_risk and disruption >= 0.70:
        return 1e12

    # Road classification hierarchy: strongly prefer physically verified National/State Highways
    if hw in {"motorway", "trunk", "primary", "secondary", "motorway_link", "trunk_link", "primary_link", "secondary_link", "osrm mapped driving route"}:
        road_suitability = 1.0  # Paved arterial highway network
    elif hw in {"tertiary", "tertiary_link"}:
        road_suitability = 3.0  # Connecting district road
    elif hw in {"unclassified", "residential"}:
        road_suitability = 12.0  # Narrow local lane; only for last-mile approach
    else:
        road_suitability = 6.0

    disruption = float(edge_data.get("disruption_probability", 0.0))
    mult = PRIORITY_RISK_MULTIPLIER.get(priority, 1.5)

    d_km = float(edge_data.get("distance_km", 1.0))
    t_min = float(edge_data.get("travel_time_min", 1.0))

    if goal == "shortest":
        # Physically shortest distance along drivable roads
        return max(0.001, (d_km * 5.0 + t_min * 0.1) * road_suitability + disruption * 3.0)
    elif goal == "fastest":
        # Fastest travel time along high-speed corridors
        return max(0.001, (t_min * 5.0 + d_km * 0.2) * road_suitability + disruption * 6.0)
    elif goal == "balanced":
        # Equal balance between travel time, distance, and safety
        return max(0.001, (t_min * 2.0 + d_km * 1.5) * road_suitability + disruption * 15.0 * mult)
    else:
        # "safest": Actively chooses lowest-hazard corridors among physically existing paved highways,
        # never diverting onto non-existent or impassable wilderness tracks
        return max(0.001, (t_min * 1.5 + d_km * 1.0) * road_suitability + disruption * 28.0 * mult)

