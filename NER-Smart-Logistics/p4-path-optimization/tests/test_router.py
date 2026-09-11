import networkx as nx
from p4_src.models import RouteRequest
from routing.cost_functions import compute_edge_cost
from p4_src.graph_builder import _normalise_osm_graph, haversine_km


def test_request_name_format():
    r = RouteRequest.model_validate({"source":"Guwahati","destination":"Tawang","priority":"critical"})
    assert r.source_name == "Guwahati"
    assert r.dest_name == "Tawang"
    assert r.priority == "critical"


def test_request_coordinate_format():
    r = RouteRequest.model_validate({"origin":{"latitude":26.14,"longitude":91.73},"destination":{"latitude":27.58,"longitude":91.86}})
    assert r.origin_lat == 26.14
    assert r.dest_lng == 91.86


def test_real_graph_normalisation_preserves_geometry():
    G=nx.MultiDiGraph()
    G.add_node(1,x=91.7,y=26.1); G.add_node(2,x=91.8,y=26.2)
    G.add_edge(1,2,key=0,length=1000,highway="primary")
    H=_normalise_osm_graph(G)
    assert H.number_of_nodes()==2 and H.number_of_edges()==1
    e=H[1][2]
    assert e["mode"]=="road" and e["distance_km"]==1.0 and e["max_weight_tons"]>=100


def test_risk_penalty_changes_cost():
    safe={"distance_km":10,"travel_time_min":20,"disruption_probability":0.0,"mode":"road","max_weight_tons":100}
    risky={**safe,"disruption_probability":0.5}
    assert compute_edge_cost(risky)>compute_edge_cost(safe)


def test_high_risk_edge_can_be_blocked():
    e={"distance_km":10,"travel_time_min":20,"disruption_probability":0.9,"mode":"road","max_weight_tons":100}
    assert compute_edge_cost(e,avoid_high_risk=True)>1e11


def test_weight_restriction_blocks_edge():
    e={"distance_km":10,"travel_time_min":20,"disruption_probability":0,"mode":"road","max_weight_tons":5}
    assert compute_edge_cost(e,vehicle_weight_tons=10)>1e11


def test_haversine_is_physical_distance():
    assert 0 < haversine_km(26.1445,91.7362,27.586,91.859) < 200
