"""Real-network route optimiser.

Important design rule: the route returned to the frontend is the exact OSM
edge geometry selected by the optimiser.  We do not route again through OSRM
using a few sampled waypoints, which could silently replace the safe route.
"""
from __future__ import annotations
import logging
import uuid
from typing import Any, List, Tuple
import math
import networkx as nx
from p4_src.config import MAX_ALTERNATIVE_ROUTES, MAX_SNAP_DISTANCE_KM, ROUTE_CORRIDOR_BUFFER_KM
from p4_src.geocoder import geocode, reverse_geocode
from p4_src.graph_builder import build_road_graph, find_nearest_node, haversine_km
from p4_src.models import RouteRequest, RouteResponse
from p4_src.risk_engine import fetch_regional_risk, get_risk_for_point
from p4_src.news_intelligence import fetch_live_disaster_news, news_status
from p4_src.official_data import nrsc_metadata, fetch_imd_cap_alerts
from p4_src.transit import railway_feed_status
from routing.cost_functions import compute_edge_cost

logger = logging.getLogger(__name__)


def _corridor_bbox(origin: Tuple[float, float], destination: Tuple[float, float]) -> Tuple[float, float, float, float]:
    lat1, lon1 = origin; lat2, lon2 = destination
    mid = (lat1 + lat2) / 2
    b_lat = ROUTE_CORRIDOR_BUFFER_KM / 111.0
    b_lon = ROUTE_CORRIDOR_BUFFER_KM / max(111.0 * math.cos(math.radians(mid)), 20)
    return max(lat1, lat2)+b_lat, min(lat1, lat2)-b_lat, max(lon1, lon2)+b_lon, min(lon1, lon2)-b_lon


def _geometry_to_latlng(data: dict, u_data: dict, v_data: dict) -> List[List[float]]:
    geom = data.get("geometry")
    if geom is not None and hasattr(geom, "coords"):
        return [[round(float(lat), 6), round(float(lon), 6)] for lon, lat in geom.coords]
    return [
        [round(float(u_data.get("y", 0)), 6), round(float(u_data.get("x", 0)), 6)],
        [round(float(v_data.get("y", 0)), 6), round(float(v_data.get("x", 0)), 6)],
    ]


class RouteOptimizer:
    def __init__(self, force_fallback: bool = False) -> None:
        self.graph: nx.DiGraph | None = None
        self._graph_key = None
        logger.info("RouteOptimizer initialised (graphs are loaded per route corridor)")

    def _resolve_coords(self, req: RouteRequest):
        if req.origin_lat is not None and req.origin_lng is not None:
            o = (req.origin_lat, req.origin_lng); on = reverse_geocode(*o)
        elif req.source_name:
            o = geocode(req.source_name); on = req.source_name.strip().title()
        else: raise ValueError("Origin / source is required")
        if req.dest_lat is not None and req.dest_lng is not None:
            d = (req.dest_lat, req.dest_lng); dn = reverse_geocode(*d)
        elif req.dest_name:
            d = geocode(req.dest_name); dn = req.dest_name.strip().title()
        else: raise ValueError("Destination is required")
        for name, (lat, lon) in (("origin", o), ("destination", d)):
            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                raise ValueError(f"Invalid {name} coordinates")
        return o, d, on, dn

    def _enrich_with_risk(self, bbox, origin_name: str, destination_name: str, origin: Tuple[float, float], destination: Tuple[float, float]) -> list[dict]:
        news_events = fetch_live_disaster_news(origin_name, destination_name, origin, destination)
        risk_grid = fetch_regional_risk(bbox, news_events=news_events)
        assert self.graph is not None
        for u, v, data in self.graph.edges(data=True):
            a = self.graph.nodes[u]; b = self.graph.nodes[v]
            lat = (float(a.get("y", 0)) + float(b.get("y", 0))) / 2
            lon = (float(a.get("x", 0)) + float(b.get("x", 0))) / 2
            risk = get_risk_for_point(lat, lon, risk_grid)
            # Refine live-news matching against the actual OSM edge geometry
            # instead of only the coarse risk-grid point.
            from p4_src.news_intelligence import news_risk_for_point, haversine_km
            news_score, incidents = news_risk_for_point(lat, lon, news_events)
            geom = data.get("geometry")
            samples = []
            if geom is not None and hasattr(geom, "coords"):
                pts = list(geom.coords)
                stride = max(1, len(pts) // 12)
                samples = [(float(y), float(x)) for x, y in pts[::stride]]
                if pts:
                    samples.append((float(pts[-1][1]), float(pts[-1][0])))
            exact_incidents = []
            exact_news = 0.0
            for ev in news_events:
                if not ev.get("geolocated"): continue
                d = min((haversine_km(float(y), float(x), float(ev["latitude"]), float(ev["longitude"])) for y,x in samples), default=9999.0)
                if d <= 55.0:
                    score = max(0.0, float(ev.get("severity", .3))*float(ev.get("confidence", .6))*(1.0-d/55.0))
                    exact_news = max(exact_news, score)
                    item = dict(ev); item["distance_from_route_km"] = round(d,1); exact_incidents.append(item)
            exact_incidents.sort(key=lambda x:(-float(x.get("severity",0)), x.get("distance_from_route_km",9999)))
            data.update(risk)
            data["news_risk"] = round(max(float(risk.get("news_risk",0)), exact_news),3)
            data["disruption_probability"] = round(max(float(risk.get("disruption_probability",0)), exact_news),3)
            data["live_incidents"] = exact_incidents[:8] if exact_incidents else incidents
        return news_events

    def _compute_costs(self, req: RouteRequest) -> None:
        assert self.graph is not None
        route_goal = getattr(req, "goal", "safest")
        for _, _, data in self.graph.edges(data=True):
            data["cost"] = compute_edge_cost(
                data, req.priority, req.avoid_high_risk_roads,
                req.max_vehicle_weight_tons, req.transport_mode,
                goal=route_goal,
            )

    def _find_routes(self, source, target, k=3) -> List[list]:
        assert self.graph is not None
        routes = []
        try:
            first = nx.dijkstra_path(self.graph, source, target, weight="cost")
            routes.append(first)
        except nx.NetworkXNoPath:
            return []
        # Use edge penalties to generate genuinely different alternatives.
        work = self.graph.copy()
        for _ in range(k - 1):
            for u, v in zip(routes[-1], routes[-1][1:]):
                if work.has_edge(u, v): work[u][v]["cost"] *= 4.0
            try:
                p = nx.dijkstra_path(work, source, target, weight="cost")
                if p not in routes: routes.append(p)
            except nx.NetworkXNoPath:
                break
        return routes

    def _summarise(self, path: list) -> dict:
        assert self.graph is not None
        dist = time_min = risk_weighted = 0.0
        ids=[]; coords=[]; steps=[]; modes=set()
        for i, n in enumerate(path):
            nd = self.graph.nodes[n]
            if i == 0 or i == len(path)-1:
                pass
            if i < len(path)-1:
                u,v=n,path[i+1]; e=self.graph[u][v]
                d=float(e.get("distance_km",0)); r=float(e.get("disruption_probability",0))
                dist += d; time_min += float(e.get("travel_time_min",0)); risk_weighted += r*d
                ids.append(e.get("road_id", f"OSM_{u}_{v}")); modes.add(e.get("mode","road"))
                seg = _geometry_to_latlng(e, self.graph.nodes[u], self.graph.nodes[v])
                if coords and seg and coords[-1] == seg[0]: coords.extend(seg[1:])
                else: coords.extend(seg)
        # Calibrate realistic commercial logistics transit duration:
        # In hill belts / mountain ghats, heavy freight travels at ~32-38 km/h.
        # On plain national highways, commercial trucks average ~50-60 km/h.
        is_hilly = any(
            ((24.0 <= float(c[0]) <= 28.8 and 88.0 <= float(c[1]) <= 97.5) or
             (29.0 <= float(c[0]) <= 36.0 and 73.0 <= float(c[1]) <= 81.0) or
             (8.0 <= float(c[0]) <= 16.0 and 73.5 <= float(c[1]) <= 77.5))
            for c in coords[::max(1, len(coords) // 12)]
        ) if coords else False

        if dist > 0:
            effective_speed = (dist / (time_min / 60.0)) if time_min > 0 else (36.0 if is_hilly else 55.0)
            if is_hilly:
                if effective_speed > 42.0:
                    time_min = (dist / 36.0) * 60.0
                elif effective_speed < 28.0:
                    time_min = (dist / 32.0) * 60.0
            else:
                if effective_speed > 68.0:
                    time_min = (dist / 56.0) * 60.0
                elif effective_speed < 38.0:
                    time_min = (dist / 50.0) * 60.0

        h = int(time_min // 60)
        m = int(round(time_min % 60))
        if m == 60:
            h += 1
            m = 0
        duration_formatted = f"{h}h {m:02d}m" if h > 0 else f"{m}m"

        risk = risk_weighted/dist if dist else 0
        # Aggregate the component risks along the selected route.
        comp = {
            "weather_risk": 0.0,
            "flood_risk": 0.0,
            "landslide_risk": 0.0,
            "imd_warning_risk": 0.0,
            "news_risk": 0.0,
            "nrsc_landslide_risk": 0.0,
        }
        detail_weight = {
            "rain_probability": 0.0,
            "rainfall_mm": 0.0,
            "temperature_c": 0.0,
            "humidity_pct": 0.0,
            "wind_kmh": 0.0,
            "river_discharge": 0.0,
            "aqi": 0.0,
            "pm2_5": 0.0,
            "pm10": 0.0,
            "uv_index": 0.0,
        }
        comp_weight = 0.0
        condition_weights = {}
        source_weights = {}
        rain_hotspots = []
        is_route_raining = False
        seen_hotspot_coords = set()

        for u, v in zip(path, path[1:]):
            e = self.graph[u][v]
            w = float(e.get("distance_km", 0.0))
            comp_weight += w
            for key in comp:
                comp[key] += float(e.get(key, 0.0) or 0.0) * w
            for key in detail_weight:
                value = e.get(key)
                if isinstance(value, (int, float)):
                    detail_weight[key] += float(value) * w
            condition = e.get("weather_condition")
            if condition:
                condition_weights[condition] = condition_weights.get(condition, 0.0) + w
            source = e.get("landslide_source")
            if source:
                source_weights[source] = source_weights.get(source, 0.0) + w

            # Collect rain hotspots for interactive map stickers
            is_rain = bool(e.get("is_raining", False))
            prob = float(e.get("rain_probability", 0.0) or 0.0)
            precip = float(e.get("rainfall_mm", 0.0) or e.get("precipitation", 0.0) or 0.0)
            if is_rain or prob >= 35.0 or precip > 0.1:
                if is_rain or precip > 0.15:
                    is_route_raining = True
                u_node = self.graph.nodes[u]
                lat = round(float(u_node.get("y", 0.0)), 4)
                lng = round(float(u_node.get("x", 0.0)), 4)
                coord_key = (round(lat, 2), round(lng, 2))
                if coord_key not in seen_hotspot_coords and len(rain_hotspots) < 8:
                    seen_hotspot_coords.add(coord_key)
                    rain_hotspots.append({
                        "lat": lat,
                        "lng": lng,
                        "condition": e.get("weather_condition", "Rain / Showers"),
                        "precipitation_mm": round(precip, 2),
                        "rain_probability": round(prob, 1),
                        "is_raining": is_rain or precip > 0.1,
                    })

        if comp_weight:
            comp = {k: round(v / comp_weight, 3) for k, v in comp.items()}
            for key in detail_weight:
                detail_weight[key] = round(detail_weight[key] / comp_weight, 2)
        comp["weather_condition"] = max(condition_weights, key=condition_weights.get) if condition_weights else "Mainly clear"
        comp["landslide_source"] = max(source_weights, key=source_weights.get) if source_weights else None
        comp.update(detail_weight)

        from p4_src.risk_engine import _aqi_category, _uv_category
        aqi_val = int(round(comp.get("aqi", 48.0) or 48.0))
        uv_val = round(comp.get("uv_index", 3.2) or 3.2, 1)
        comp["aqi"] = aqi_val
        comp["aqi_category"] = _aqi_category(aqi_val)
        comp["uv_index"] = uv_val
        comp["uv_category"] = _uv_category(uv_val)
        comp["is_raining"] = is_route_raining
        comp["rain_hotspots"] = rain_hotspots

        hourly_forecast_data = []
        for u, v in zip(path, path[1:]):
            hf = self.graph[u][v].get("hourly_forecast")
            if hf:
                hourly_forecast_data = hf
                break
        comp["hourly_forecast"] = hourly_forecast_data

        rain_prob = comp.get("rain_probability", 0.0) or 0.0
        rain_mm = comp.get("rainfall_mm", 0.0) or 0.0
        if is_route_raining:
            comp["rain_forecast_summary"] = f"Active rain detected along corridor ({rain_mm:.1f} mm precip, {rain_prob:.0f}% prob). Wet road precautions advised."
        elif rain_prob >= 50.0:
            comp["rain_forecast_summary"] = f"Elevated rain likelihood ({rain_prob:.0f}% probability, {rain_mm:.1f} mm forecast)."
        elif rain_prob >= 20.0:
            comp["rain_forecast_summary"] = f"Isolated showers possible ({rain_prob:.0f}% probability)."
        else:
            comp["rain_forecast_summary"] = f"Dry & clear transit window ({rain_prob:.0f}% rain likelihood)."

        flood_val = comp.get("flood_risk", 0.05) or 0.05
        hum_val = comp.get("humidity_pct", 60.0) or 60.0
        wind_val = comp.get("wind_kmh", 12.0) or 12.0
        discharge_val = comp.get("river_discharge", 0.0) or 0.0
        if flood_val >= 0.65:
            comp["flood_summary"] = f"CRITICAL INUNDATION: Severe waterlogging risk ({rain_mm:.1f} mm rain, {hum_val:.0f}% humidity, {wind_val:.0f} km/h winds)."
        elif flood_val >= 0.35:
            comp["flood_summary"] = f"MODERATE WATERLOGGING: Caution advised on low-lying stretches ({hum_val:.0f}% humidity, {rain_mm:.1f} mm rain)."
        elif flood_val >= 0.18:
            comp["flood_summary"] = f"LOW FLOOD HAZARD: Minor surface runoff ({hum_val:.0f}% humidity, {wind_val:.0f} km/h winds)."
        else:
            comp["flood_summary"] = f"NORMAL RUNOFF: Low flood risk ({hum_val:.0f}% humidity, {wind_val:.0f} km/h winds, clear drainage)."

        incidents = []
        seen_incidents = set()
        for u, v in zip(path, path[1:]):
            for item in self.graph[u][v].get("live_incidents", []) or []:
                key = (item.get("title"), item.get("source"))
                if key not in seen_incidents:
                    incidents.append(item)
                    seen_incidents.add(key)
        # Keep the full corridor news list; preview slicing happens in the UI
        comp_risk = (
            0.35 * comp.get("weather_risk", 0.05) +
            0.35 * comp.get("landslide_risk", 0.10) +
            0.20 * comp.get("flood_risk", 0.05) +
            0.10 * comp.get("news_risk", 0.0)
        )
        route_risk = round(max(0.04, min(0.95, comp_risk)), 3)
        safety_score = round(max(5.0, min(98.0, (1.0 - route_risk) * 100)), 1)
        return {"road_ids":ids,"distance_km":round(dist,1),"estimated_travel_time_minutes":round(time_min,0),
                "duration_formatted":duration_formatted,
                "route_risk":route_risk,"safety_score":safety_score,
                "coordinates":coords,"modes":sorted(modes), "live_incidents":incidents, **comp}

    def optimize(self, req: RouteRequest) -> RouteResponse:
        origin, dest, oname, dname = self._resolve_coords(req)
        if req.transport_mode not in {"road", "multimodal"}:
            raise ValueError("Use road or multimodal. Passenger rail requires a configured Indian Railways/GTFS service feed; railway tracks alone are not treated as train service.")
        if haversine_km(origin[0], origin[1], dest[0], dest[1]) < 0.05:
            raise ValueError("Origin and destination resolve to the same location")
        bbox = _corridor_bbox(origin, dest)
        graph = build_road_graph(origin, dest, use_cache=True, force_fallback=False, include_ferries=req.transport_mode == "multimodal")
        self.graph = graph
        onode, od = find_nearest_node(graph, *origin); dnode, dd = find_nearest_node(graph, *dest)
        if onode is None or dnode is None: raise ValueError("No real road network found near origin/destination")
        if od > MAX_SNAP_DISTANCE_KM or dd > MAX_SNAP_DISTANCE_KM:
            raise ValueError(f"Location is too far from a mapped drivable road (origin snap {od:.1f} km, destination snap {dd:.1f} km). Provide a road-accessible point.")
        news_events = self._enrich_with_risk(bbox, oname, dname, origin, dest)
        self._compute_costs(req)
        routes = self._find_routes(onode,dnode,MAX_ALTERNATIVE_ROUTES)
        if not routes: raise ValueError(f"No physically connected road route found from {oname} to {dname}")
        best=self._summarise(routes[0])
        alt_list = []
        for idx, alt_path in enumerate(routes[1:], start=2):
            s = self._summarise(alt_path)
            s["option_id"] = f"alt_{idx}"
            s["option_name"] = f"Alternative Option {idx-1}"
            alt_list.append(s)
        waypoints=[]
        for n in routes[0]:
            nd=graph.nodes[n]
            waypoints.append({"node":n,"name":str(nd.get("place", n)).replace("_"," ").title(),"lat":float(nd.get("y",0)),"lng":float(nd.get("x",0))})
        instructions=[]
        for i,wp in enumerate(waypoints):
            instructions.append({"step":i+1,"type":"waypoint","instruction":("Start" if i==0 else "Arrive" if i==len(waypoints)-1 else "Continue on mapped road network"),"road":wp["name"],"distance_meters":0,"duration_seconds":0,"lat":wp["lat"],"lng":wp["lng"]})
        best_provider = str(graph.graph.get("routing_provider", "OpenStreetMap / OSMnx / Overpass"))
        eta_h = round(best["estimated_travel_time_minutes"] / 60.0, 1)
        return RouteResponse.create(
            route_id=f"ROUTE_{uuid.uuid4().hex[:6].upper()}", origin=oname,destination=dname,
            transport_mode=req.transport_mode,transit_modes=best["modes"],road_ids=best["road_ids"],
            departure_date=getattr(req, "departure_date", None),
            departure_time=getattr(req, "departure_time", None),
            route=best["road_ids"],waypoints=waypoints,route_coordinates=best["coordinates"],
            navigation_instructions=instructions,distance_km=best["distance_km"],
            estimated_travel_time_minutes=best["estimated_travel_time_minutes"],
            eta_hours=eta_h,duration_hours=eta_h,
            duration_formatted=best.get("duration_formatted"),
            route_risk=best["route_risk"],
            safety_score=best["safety_score"],
            alternative_routes_available=max(0,len(routes)-1),
            alternatives=alt_list,
            weather_risk=best.get("weather_risk"),
            weather_condition=best.get("weather_condition"),
            rain_probability=best.get("rain_probability"),
            rainfall_mm=best.get("rainfall_mm"),
            temperature_c=best.get("temperature_c"),
            humidity_pct=best.get("humidity_pct"),
            wind_kmh=best.get("wind_kmh"),
            aqi=best.get("aqi"),
            aqi_category=best.get("aqi_category"),
            pm2_5=best.get("pm2_5"),
            pm10=best.get("pm10"),
            uv_index=best.get("uv_index"),
            uv_category=best.get("uv_category"),
            is_raining=best.get("is_raining"),
            rain_forecast_summary=best.get("rain_forecast_summary"),
            rain_hotspots=best.get("rain_hotspots", []),
            hourly_forecast=best.get("hourly_forecast", []),
            flood_risk=best.get("flood_risk"),
            flood_summary=best.get("flood_summary"),
            river_discharge=best.get("river_discharge"),
            landslide_risk=best.get("landslide_risk"),
            landslide_source=best.get("landslide_source"),
            nrsc_landslide_risk=best.get("nrsc_landslide_risk"),
            imd_warning_risk=best.get("imd_warning_risk"),
            news_risk=best.get("news_risk"), live_incidents=best.get("live_incidents", []),
            disaster_news=news_events,
            data_sources=[best_provider, "Open-Meteo Weather", "Open-Meteo Air Quality", "Open-Meteo Flood", "IMD public CAP warnings", "NRSC/ISRO Bhuvan landslide hazard layer", "Live disaster news: GDELT GKG GeoJSON + GDELT DOC + Google News RSS", "Indian Railways service feed status: " + str(railway_feed_status().get("enabled"))]
            ,data_provenance={"imd": "https://wis2box.imd.gov.in/oapi/collections/messages/items", "nrsc": nrsc_metadata(), "railways": railway_feed_status(), "news": news_status(), "live_news_events_fetched": len(news_events), "imd_active_alerts": len(fetch_imd_cap_alerts())}
        )
