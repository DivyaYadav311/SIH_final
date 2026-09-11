"""Real ferry and railway infrastructure helpers.

Roads remain the default. Ferry links come from OSM `route=ferry` and railway
infrastructure from OSM `railway=*`. Passenger service is only enabled when a
real timetable/GTFS feed is configured; track geometry alone is never treated
as a train service.
"""
from __future__ import annotations
import logging, os, zipfile, io, csv
from pathlib import Path
from typing import Optional
import networkx as nx

log = logging.getLogger(__name__)
GTFS_PATH = os.getenv("INDIAN_RAILWAYS_GTFS_PATH", "")
GTFS_URL = os.getenv("INDIAN_RAILWAYS_GTFS_URL", "")


def _parse_gtfs(path: str) -> dict:
    out={}
    with zipfile.ZipFile(path) as z:
        names=set(z.namelist())
        if "stops.txt" not in names or "stop_times.txt" not in names or "trips.txt" not in names:
            raise ValueError("GTFS must contain stops.txt, stop_times.txt and trips.txt")
        def read(name):
            with z.open(name) as f: return list(csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig")))
        out["stops"]=read("stops.txt")
        out["trips"]=read("trips.txt")
        out["stop_times"]=read("stop_times.txt")
    return out


def railway_feed_status() -> dict:
    if GTFS_PATH and os.path.exists(GTFS_PATH):
        try:
            d=_parse_gtfs(GTFS_PATH)
            return {"enabled":True,"type":"GTFS","path":GTFS_PATH,"stations":len(d["stops"]),"trips":len(d["trips"]),"source":"Configured Indian Railways timetable feed"}
        except Exception as e: return {"enabled":False,"error":str(e)}
    if GTFS_URL: return {"enabled":True,"type":"GTFS_URL","url":GTFS_URL,"note":"Feed will be downloaded on first rail/multimodal request."}
    return {"enabled":False,"note":"No passenger timetable configured. OSM railway tracks are available as infrastructure context only; no train service is fabricated."}


def add_osm_ferry_network(base: nx.DiGraph, bbox: tuple[float,float,float,float]) -> tuple[nx.DiGraph, int]:
    """Add real OSM ferry geometry and connect only mapped ferry endpoints to nearby drivable roads.

    bbox is (north, south, east, west). A ferry edge is never a straight-line
    shortcut: its geometry comes from an OSM `route=ferry` way/relation.
    """
    try:
        import osmnx as ox
        north,south,east,west=bbox
        fs=ox.features_from_bbox((west,south,east,north), {"route":"ferry"})
        added=0
        for idx,row in fs.iterrows():
            geom=row.get("geometry")
            if geom is None: continue
            geoms = list(geom.geoms) if geom.geom_type == "MultiLineString" else [geom]
            for line in geoms:
                if not hasattr(line,"coords"): continue
                pts=list(line.coords)
                if len(pts)<2: continue
                prev=None
                for x,y in pts:
                    n=f"ferry_{idx}_{round(x,6)}_{round(y,6)}"
                    base.add_node(n,x=float(x),y=float(y),place="Ferry route",transport_node=True)
                    if prev:
                        # Approximate ferry speed only for time costing; the
                        # distance itself follows the mapped water geometry.
                        from p4_src.graph_builder import haversine_km
                        py,px=base.nodes[prev]["y"],base.nodes[prev]["x"]
                        d=haversine_km(py,px,float(y),float(x))
                        attrs=dict(mode="ferry",distance_km=d,travel_time_min=d/15*60,
                                   road_id=f"OSM_FERRY_{idx}",max_weight_tons=1000.0,
                                   ferry_name=str(row.get("name") or row.get("ref") or "OSM ferry"),
                                   ferry_operator=str(row.get("operator") or ""))
                        base.add_edge(prev,n,**attrs)
                        added+=1
                    prev=n
        # Connect ferry endpoints to the nearest actual road node. This is
        # intentionally limited to 2 km so we never create an implausible
        # road-to-river teleport.
        import osmnx as ox
        ferry_nodes=[n for n,d in base.nodes(data=True) if d.get("transport_node")]
        road_nodes=[n for n,d in base.nodes(data=True) if not d.get("transport_node") and "x" in d and "y" in d]
        endpoint_nodes = []
        for n, d in base.nodes(data=True):
            if d.get("transport_node"):
                # Ferry endpoint has degree 1 within the ferry network.
                ferry_neighbors=[x for x in base.successors(n) if base.nodes[x].get("transport_node")]
                if len(ferry_neighbors) <= 1: endpoint_nodes.append(n)
        for fn in endpoint_nodes:
            fd=base.nodes[fn]
            try:
                rn=min(road_nodes, key=lambda n: (float(base.nodes[n]["x"])-float(fd["x"]))**2 + (float(base.nodes[n]["y"])-float(fd["y"]))**2)
                rd=base.nodes[rn]
                from p4_src.graph_builder import haversine_km
                d=haversine_km(float(fd["y"]),float(fd["x"]),float(rd["y"]),float(rd["x"]))
                if d <= 0.75:
                    base.add_edge(rn,fn,mode="transfer",distance_km=d,travel_time_min=d/25*60,road_id="FERRY_TERMINAL_TRANSFER",max_weight_tons=1000.0)
                    base.add_edge(fn,rn,mode="transfer",distance_km=d,travel_time_min=d/25*60,road_id="FERRY_TERMINAL_TRANSFER",max_weight_tons=1000.0)
            except Exception: pass
        return base,added
    except Exception as exc:
        log.info("OSM ferry network unavailable: %s", exc)
        return base,0

RAIL_API_KEY = os.getenv("INDIAN_RAIL_API_KEY", "")
RAIL_API_BASE = os.getenv("INDIAN_RAIL_API_BASE", "https://indianrailapi.com/api/v2")


def fetch_train_schedule(train_number: str) -> dict:
    """Fetch a train schedule when an Indian Rail API test/live key is configured.

    The official Indian Railways enquiry site remains the authoritative human
    reference. Third-party API access is optional because Indian Railways does
    not expose a broadly open developer timetable API.
    """
    if not RAIL_API_KEY:
        return {"enabled": False, "message": "Set INDIAN_RAIL_API_KEY to enable machine-readable train schedules. No train service is fabricated."}
    import httpx
    url=f"{RAIL_API_BASE}/TrainSchedule/apikey/{RAIL_API_KEY}/TrainNumber/{train_number}/"
    try:
        r=httpx.get(url,timeout=15,follow_redirects=True); r.raise_for_status(); data=r.json()
        return {"enabled": True, "provider":"Indian Rail API (third-party)", "train_number":train_number, "data":data}
    except Exception as exc:
        return {"enabled": True, "provider":"Indian Rail API (third-party)", "error":str(exc)}
