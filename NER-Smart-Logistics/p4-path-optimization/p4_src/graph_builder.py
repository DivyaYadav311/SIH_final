"""Build a *real* travel network from OpenStreetMap.

The old project mixed real OSM roads with hand-written straight-line edges.
That made the optimiser capable of selecting routes that did not physically
exist.  This module deliberately avoids that: production routing uses only
actual OSM road edges and their geometries.

Coverage is dynamic.  A request for Delhi -> Tawang downloads/caches a road
corridor around those two points instead of using a fixed Northeast bbox.
"""
from __future__ import annotations

import logging
import math
import os
import pickle
import re
from pathlib import Path
from typing import Optional, Tuple

import networkx as nx

from p4_src.config import (
    DEFAULT_SPEED_KMH,
    ROAD_SPEED_KMH,
    ROUTE_CORRIDOR_BUFFER_KM,
    ROUTE_MAX_DOWNLOAD_AREA_KM2,
    GRAPH_CACHE_DIR,
    OSM_TILE_LENGTH_KM,
    OSM_TILE_BUFFER_KM,
    OVERPASS_TIMEOUT_SECONDS,
    OVERPASS_ENDPOINTS,
    OSRM_ROUTING_URL,
    OSRM_TIMEOUT_SECONDS,
    OSRM_ALTERNATIVES,
)

logger = logging.getLogger(__name__)


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _road_speed(highway) -> float:
    if isinstance(highway, list):
        highway = highway[0] if highway else "unclassified"
    return float(ROAD_SPEED_KMH.get(str(highway), DEFAULT_SPEED_KMH))


def _safe_cache_name(lat1: float, lon1: float, lat2: float, lon2: float) -> str:
    raw = f"{lat1:.3f}_{lon1:.3f}_{lat2:.3f}_{lon2:.3f}"
    return re.sub(r"[^0-9A-Za-z_.-]+", "_", raw) + ".pkl"


def _bbox_for_corridor(
    origin: Tuple[float, float],
    destination: Tuple[float, float],
    buffer_km: float,
) -> Tuple[float, float, float, float]:
    """Return north,south,east,west bbox around an origin/destination corridor."""
    lat1, lon1 = origin
    lat2, lon2 = destination
    mid_lat = (lat1 + lat2) / 2.0
    lat_buffer = buffer_km / 111.0
    lon_buffer = buffer_km / max(111.0 * math.cos(math.radians(mid_lat)), 20.0)
    return (
        max(lat1, lat2) + lat_buffer,
        min(lat1, lat2) - lat_buffer,
        max(lon1, lon2) + lon_buffer,
        min(lon1, lon2) - lon_buffer,
    )


def _bbox_area_km2(bbox: Tuple[float, float, float, float]) -> float:
    north, south, east, west = bbox
    mid_lat = (north + south) / 2.0
    height = abs(north - south) * 111.0
    width = abs(east - west) * 111.0 * max(math.cos(math.radians(mid_lat)), 0.2)
    return height * width


def _load_cache(path: Path) -> Optional[nx.DiGraph]:
    try:
        if path.exists():
            with path.open("rb") as fh:
                graph = pickle.load(fh)
            if isinstance(graph, nx.DiGraph) and graph.number_of_nodes() > 0:
                logger.info("Loaded cached OSM graph: %s", path)
                return graph
    except Exception as exc:
        logger.warning("Could not read graph cache %s: %s", path, exc)
    return None


def _save_cache(path: Path, graph: nx.DiGraph) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with tmp.open("wb") as fh:
        pickle.dump(graph, fh, protocol=pickle.HIGHEST_PROTOCOL)
    tmp.replace(path)


def _normalise_osm_graph(g_multi) -> nx.DiGraph:
    """Keep the shortest real directed OSM edge and preserve its geometry."""
    g = nx.DiGraph()
    for node, data in g_multi.nodes(data=True):
        g.add_node(node, **data)

    for u, v, key, data in g_multi.edges(keys=True, data=True):
        length_m = float(data.get("length", 0) or 0)
        if length_m <= 0:
            continue
        highway = data.get("highway", "unclassified")
        if isinstance(highway, list):
            highway = highway[0]
        hw_str = str(highway).lower()
        if hw_str in {"track", "path", "footway", "pedestrian", "service", "living_street", "steps", "cycleway", "bridleway", "corridor", "abandoned", "proposed", "construction", "escape", "raceway", "bus_guideway", "footpath"}:
            continue
        if data.get("access") in {"no", "private"}:
            continue
        speed = _road_speed(highway)
        travel_min = (length_m / 1000.0) / max(speed, 1.0) * 60.0


        # OSMnx normally stores a shapely LineString here.  Keep it in the
        # graph so the frontend can draw the exact road, not a straight line.
        attrs = dict(data)
        attrs.update(
            {
                "road_id": f"OSM_{u}_{v}_{key}",
                "distance_km": round(length_m / 1000.0, 3),
                "travel_time_min": round(travel_min, 2),
                "speed_kmh": speed,
                "highway": highway,
                "mode": "road",
                "max_weight_tons": _parse_max_weight(data),
                "accessibility_score": 100.0,
                "disruption_probability": 0.0,
            }
        )

        if not g.has_edge(u, v) or attrs["distance_km"] < g[u][v].get("distance_km", float("inf")):
            g.add_edge(u, v, **attrs)
    return g


def _parse_max_weight(data: dict) -> float:
    value = data.get("maxweight") or data.get("maxweight:conditional")
    if value is None:
        # No tag means "unknown", not a 40-ton physical limit.  Keep a high
        # value so normal road edges remain usable while tagged restrictions
        # are respected.
        return 1000.0
    try:
        match = re.search(r"([0-9]+(?:\.[0-9]+)?)", str(value).replace(",", "."))
        return float(match.group(1)) if match else 1000.0
    except Exception:
        return 1000.0


def _download_one_osm_tile(bbox: Tuple[float, float, float, float], tile_cache: Optional[Path] = None):
    """Download one small real OSM road tile, with Overpass endpoint fallback."""
    if tile_cache is not None:
        cached = _load_cache(tile_cache)
        if cached is not None:
            return cached

    try:
        import osmnx as ox
    except ImportError:
        raise RuntimeError("OSMnx is not installed. Run: pip install -r requirements.txt")

    north, south, east, west = bbox
    last_exc = None

    # OSMnx's public Overpass endpoint can be busy or rate-limited. Try a few
    # public endpoints before failing the tile. This is especially useful for
    # the long Northeast corridors that need several small requests.
    for endpoint in OVERPASS_ENDPOINTS:
        try:
            ox.settings.overpass_url = endpoint
            ox.settings.requests_timeout = OVERPASS_TIMEOUT_SECONDS
            logger.info(
                "Downloading OSM tile via %s: N=%.4f S=%.4f E=%.4f W=%.4f",
                endpoint, north, south, east, west,
            )
            try:
                g_multi = ox.graph.graph_from_bbox(
                    bbox=(west, south, east, north),
                    network_type="drive",
                    simplify=True,
                    retain_all=False,
                )
            except (AttributeError, TypeError):
                g_multi = ox.graph_from_bbox(
                    bbox=(west, south, east, north),
                    network_type="drive",
                    simplify=True,
                    retain_all=False,
                )
            graph = _normalise_osm_graph(g_multi)
            if graph.number_of_edges() == 0:
                raise RuntimeError("OSM returned no drivable edges")
            if tile_cache is not None:
                _save_cache(tile_cache, graph)
            graph.graph["routing_provider"] = "OpenStreetMap / OSMnx / Overpass"
            return graph
        except Exception as exc:
            last_exc = exc
            logger.warning("OSM tile failed on %s: %s", endpoint, exc)

    raise RuntimeError(
        "All configured Overpass endpoints failed for this OSM tile. "
        "Try again later or use a cached graph. Last error: " + str(last_exc)
    )


def _corridor_tiles(
    origin: Tuple[float, float],
    destination: Tuple[float, float],
    buffer_km: float,
):
    """Create small overlapping boxes along the origin-destination corridor.

    This avoids asking Overpass for a huge rectangle such as all of Assam and
    Arunachal Pradesh at once. The boxes overlap so roads near tile boundaries
    remain connected after graphs are composed.
    """
    distance = haversine_km(origin[0], origin[1], destination[0], destination[1])
    count = max(1, int(math.ceil(distance / max(OSM_TILE_LENGTH_KM, 10.0))))
    tiles = []
    for i in range(count):
        t0 = i / count
        t1 = (i + 1) / count
        a = (origin[0] + (destination[0] - origin[0]) * t0,
             origin[1] + (destination[1] - origin[1]) * t0)
        b = (origin[0] + (destination[0] - origin[0]) * t1,
             origin[1] + (destination[1] - origin[1]) * t1)
        tiles.append(_bbox_for_corridor(a, b, buffer_km))
    return tiles



def _download_osrm_fallback(
    origin: Tuple[float, float],
    destination: Tuple[float, float],
    cache_path: Optional[Path] = None,
) -> Optional[nx.DiGraph]:
    """Build a real-road graph from OSRM alternatives when Overpass is unavailable.

    OSRM's alternatives are all mapped driving routes.  We keep every returned
    candidate as a branch between common origin/destination nodes, so the
    existing risk-aware Dijkstra step can compare candidates after weather,
    flood, landslide, IMD and news enrichment.
    """
    if cache_path is not None:
        cached = _load_cache(cache_path)
        if cached is not None:
            return cached

    try:
        import httpx
    except ImportError:
        logger.warning("httpx is not installed; OSRM fallback unavailable")
        return None

    lat1, lon1 = origin
    lat2, lon2 = destination
    url = f"{OSRM_ROUTING_URL}/{lon1:.6f},{lat1:.6f};{lon2:.6f},{lat2:.6f}"
    params = {
        "overview": "full",
        "geometries": "geojson",
        "steps": "true",
        "alternatives": max(1, min(OSRM_ALTERNATIVES, 3)),
    }

    try:
        logger.warning("All Overpass endpoints failed; trying real-road OSRM alternatives")
        with httpx.Client(
            timeout=OSRM_TIMEOUT_SECONDS,
            follow_redirects=True,
            headers={"User-Agent": "PravahLogistics/3.0 (contact@pravah-ner.org)"},
        ) as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            payload = response.json()

        if payload.get("code") != "Ok" or not payload.get("routes"):
            raise RuntimeError(f"OSRM returned no route: {payload.get('code', 'unknown')}")

        routes = payload["routes"]
        graph = nx.DiGraph()

        # Common endpoints guarantee that the optimizer can choose among
        # alternative route branches after risk enrichment.
        graph.add_node("osrm_origin", x=float(lon1), y=float(lat1), place="OSRM route origin")
        graph.add_node("osrm_destination", x=float(lon2), y=float(lat2), place="OSRM route destination")

        valid_routes = 0
        for ridx, route in enumerate(routes[:3]):
            coords = (route.get("geometry") or {}).get("coordinates") or []
            if len(coords) < 2:
                continue

            route_lengths = []
            for i in range(len(coords) - 1):
                x1, y1 = map(float, coords[i])
                x2, y2 = map(float, coords[i + 1])
                route_lengths.append(haversine_km(y1, x1, y2, x2))
            geom_sum = sum(route_lengths) or 1.0
            total_km = float(route.get("distance", 0.0)) / 1000.0
            total_min = float(route.get("duration", 0.0)) / 60.0

            # Calibrate realistic commercial logistics transit duration:
            # In hill belts / mountain ghats, heavy freight travels at ~32-38 km/h.
            # On plain national highways, commercial trucks average ~50-60 km/h.
            is_hilly = any(
                ((24.0 <= float(p[1]) <= 28.8 and 88.0 <= float(p[0]) <= 97.5) or
                 (29.0 <= float(p[1]) <= 36.0 and 73.0 <= float(p[0]) <= 81.0) or
                 (8.0 <= float(p[1]) <= 16.0 and 73.5 <= float(p[0]) <= 77.5))
                for p in coords[::max(1, len(coords)//10)]
            )
            raw_speed = (total_km / (total_min / 60.0)) if total_min > 0 else DEFAULT_SPEED_KMH
            if is_hilly and raw_speed > 38.0:
                total_min = (total_km / 35.0) * 60.0
            elif not is_hilly and raw_speed > 65.0:
                total_min = (total_km / 55.0) * 60.0

            first = f"osrm_{ridx}_0"
            last = f"osrm_{ridx}_{len(coords)-1}"
            # The first/last geometry points are represented by common nodes;
            # intermediate points retain the exact OSRM geometry.
            for i, pair in enumerate(coords):
                lon, lat = float(pair[0]), float(pair[1])
                node = "osrm_origin" if i == 0 else (
                    "osrm_destination" if i == len(coords) - 1 else f"osrm_{ridx}_{i}"
                )
                if node not in graph:
                    graph.add_node(node, x=lon, y=lat, place="OSRM mapped road route")

            for i, d in enumerate(route_lengths):
                u = "osrm_origin" if i == 0 else f"osrm_{ridx}_{i}"
                v = "osrm_destination" if i == len(route_lengths) - 1 else f"osrm_{ridx}_{i + 1}"
                distance_km = total_km * (d / geom_sum)
                travel_min = total_min * (d / geom_sum)
                graph.add_edge(
                    u, v,
                    road_id=f"OSRM_ALTERNATIVE_{ridx + 1}_{i}",
                    distance_km=round(distance_km, 5),
                    travel_time_min=round(travel_min, 4),
                    speed_kmh=(distance_km / travel_min * 60.0) if travel_min > 0 else DEFAULT_SPEED_KMH,
                    highway="OSRM mapped driving route",
                    mode="road",
                    max_weight_tons=1000.0,
                    accessibility_score=100.0,
                    disruption_probability=0.0,
                    osrm_alternative=ridx + 1,
                )
            valid_routes += 1

        if valid_routes == 0 or graph.number_of_edges() == 0:
            return None

        graph.graph["routing_provider"] = "OSRM public routing fallback (mapped roads; alternatives)"
        graph.graph["routing_candidates"] = valid_routes
        if cache_path is not None:
            _save_cache(cache_path, graph)

        logger.info(
            "OSRM fallback graph built from %d mapped route alternatives (%d nodes, %d edges)",
            valid_routes, graph.number_of_nodes(), graph.number_of_edges(),
        )
        return graph
    except Exception as exc:
        logger.warning("OSRM fallback failed: %s", exc)
        return None

def _download_osmnx(bbox: Tuple[float, float, float, float], origin=None, destination=None) -> Optional[nx.DiGraph]:
    """Download real OSM roads, using corridor tiling for large Northeast routes."""
    if origin is not None and destination is not None:
        tiles = _corridor_tiles(origin, destination, OSM_TILE_BUFFER_KM)
    else:
        tiles = [bbox]

    merged = nx.DiGraph()
    base = Path(GRAPH_CACHE_DIR)
    for idx, tile in enumerate(tiles):
        north, south, east, west = tile
        cache_name = _safe_cache_name(north, south, east, west)
        tile_cache = base / ("tile_" + cache_name)
        logger.info("OSM corridor tile %d/%d", idx + 1, len(tiles))
        tile_graph = _download_one_osm_tile(tile, tile_cache)
        merged = nx.compose(merged, tile_graph)

    if merged.number_of_edges() == 0:
        return None
    logger.info(
        "Combined OSM corridor graph: %d nodes, %d directed edges from %d tiles",
        merged.number_of_nodes(), merged.number_of_edges(), len(tiles),
    )
    return merged


def build_road_graph(
    origin: Optional[Tuple[float, float]] = None,
    destination: Optional[Tuple[float, float]] = None,
    use_cache: bool = True,
    force_fallback: bool = False,
    include_ferries: bool = False,
) -> nx.DiGraph:
    """Build/cache a real road graph for the requested route corridor.

    ``force_fallback`` is retained for API compatibility, but the old fake
    graph is intentionally no longer used.  If real OSM data cannot be
    obtained, a clear error is returned instead of inventing a road.
    """
    if origin is None or destination is None:
        raise ValueError("Origin and destination coordinates are required to build a real route graph")

    cache_name = _safe_cache_name(*origin, *destination)
    if include_ferries: cache_name = cache_name.replace(".pkl", "_ferry.pkl")
    cache_path = Path(GRAPH_CACHE_DIR) / cache_name
    if use_cache:
        cached = _load_cache(cache_path)
        if cached is not None:
            return cached

    bbox = _bbox_for_corridor(origin, destination, ROUTE_CORRIDOR_BUFFER_KM)
    area = _bbox_area_km2(bbox)
    if area > ROUTE_MAX_DOWNLOAD_AREA_KM2:
        logger.info("Corridor area (%.0f km²) exceeds Overpass tile limit; routing via high-performance mapped OSRM network", area)
        fallback_cache = Path(GRAPH_CACHE_DIR) / (cache_name.replace(".pkl", "_osrm.pkl"))
        graph = _download_osrm_fallback(origin, destination, fallback_cache)
        if graph is not None and graph.number_of_edges() > 0:
            if include_ferries:
                try:
                    from p4_src.transit import add_osm_ferry_network
                    graph, _ = add_osm_ferry_network(graph, bbox)
                except Exception:
                    pass
            _save_cache(cache_path, graph)
            return graph

    try:
        graph = _download_osmnx(bbox, origin=origin, destination=destination)
    except Exception as exc:
        logger.warning("OSM/Overpass corridor download failed; using real-road fallback: %s", exc)
        graph = None

    if graph is None or graph.number_of_edges() == 0:
        # Public Overpass can be temporarily unavailable. Prefer a real-road
        # OSRM fallback over a fake straight-line graph so the demo can still
        # return a physically travelable route.
        fallback_cache = Path(GRAPH_CACHE_DIR) / (cache_name.replace(".pkl", "_osrm.pkl"))
        graph = _download_osrm_fallback(origin, destination, fallback_cache)
    if graph is None or graph.number_of_edges() == 0:
        raise RuntimeError(
            "No real drivable route could be obtained from OSM/Overpass or the OSRM fallback"
        )
    graph.graph.setdefault("routing_provider", "OpenStreetMap / OSMnx / Overpass")
    if include_ferries:
        try:
            from p4_src.transit import add_osm_ferry_network
            graph, ferry_edges = add_osm_ferry_network(graph, bbox)
            logger.info("Added %d real OSM ferry segments", ferry_edges)
        except Exception as exc:
            logger.warning("Ferry enrichment failed: %s", exc)
    _save_cache(cache_path, graph)
    return graph


def find_nearest_node(G: nx.DiGraph, lat: float, lng: float) -> Tuple[object, float]:
    """Return nearest real road node and snap distance in km."""
    try:
        import osmnx as ox
        node = ox.distance.nearest_nodes(G, X=lng, Y=lat)
        data = G.nodes[node]
        nlat, nlng = float(data["y"]), float(data["x"])
        return node, haversine_km(lat, lng, nlat, nlng)
    except Exception:
        best_node = None
        best_dist = float("inf")
        for node, data in G.nodes(data=True):
            if "y" not in data or "x" not in data:
                continue
            d = haversine_km(lat, lng, float(data["y"]), float(data["x"]))
            if d < best_dist:
                best_node, best_dist = node, d
        return best_node, best_dist
