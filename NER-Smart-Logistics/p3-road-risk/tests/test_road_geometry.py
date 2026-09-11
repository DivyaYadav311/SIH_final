import pytest

from p3_src.satellite_cv.road_geometry import (DEFAULT_PBF, _fallback, _score_candidate, _select,
    _tokens, normalize_highway_ref, normalize_road_name, road_identity, validate_geometry)


def candidate(identifier, distance, **tags):
    return _score_candidate({"road_name": "Example Valley Road", "road_type": "road"}, {"id": identifier, "tags": {"highway": "primary", **tags}, "distance_from_event": distance, "geometry": [{"lat": 10.0, "lon": 76.0}, {"lat": 10.001, "lon": 76.001}]})


@pytest.mark.parametrize(("raw", "expected"), [("NH-7", "NH-7"), ("NH 7", "NH-7"), ("NH7", "NH-7"), ("National Highway 7", "NH-7"), ("SH-10", "SH-10"), ("State Highway 10", "SH-10")])
def test_explicit_highway_reference_normalization(raw, expected):
    assert normalize_highway_ref(raw) == expected


def test_road_name_normalization_and_narrative_detection():
    assert normalize_road_name(" Adivaram - Vythiri Road ") == "adivaram vythiri road"
    assert road_identity({"road_name": "Road blocked and electric pole damaged."})["road_name_quality"] == "NARRATIVE_TEXT"
    assert road_identity({"road_name": None})["road_name_quality"] == "EMPTY"
    assert road_identity({"road_name": "Peringalkuthu dam"})["road_name_quality"] == "UNCERTAIN"


def test_matching_tokens_ignore_generic_short_words():
    assert _tokens("Adivaram - Vythiri Road") == {"adivaram", "vythiri"}


def test_candidate_filtering_and_scoring():
    scored = candidate(42, 50, name="Example Valley Road")
    assert scored["matching_confidence"] == "high" and scored["name_similarity"] == 1
    excluded = candidate(43, 5, highway="footway")
    assert excluded["rejection_reason"] == "excluded non-road highway=footway"


def test_coordinate_only_candidate_can_never_be_high():
    result = _select({"road_name": "Road blocked and electric pole damaged."}, [candidate(1, 20)])
    assert result["match_status"] == "MEDIUM_CONFIDENCE"


def test_ambiguous_nearby_candidates_are_not_selected():
    result = _select({"road_name": "Road blocked and electric pole damaged."}, [candidate(1, 20), candidate(2, 25)])
    assert result["match_status"] == "AMBIGUOUS" and result["selected_candidate"] is None


def test_no_forced_match_for_single_distant_coordinate_candidate():
    result = _select({"road_name": "Road blocked and electric pole damaged."}, [candidate(1, 120)])
    assert result["match_status"] == "COORDINATE_FALLBACK" and result["selected_candidate"] is None


def test_deterministic_ordering_for_equal_distance_candidates():
    result = _select({"road_name": "Road blocked and electric pole damaged."}, [candidate(9, 20), candidate(1, 20)])
    assert result["match_status"] == "AMBIGUOUS"


def test_geometry_validation():
    assert validate_geometry([{"lat": 1, "lon": 2}, {"lat": 1.1, "lon": 2.1}])
    assert not validate_geometry([{"lat": 1, "lon": 2}])
    assert not validate_geometry([{"lat": 91, "lon": 2}, {"lat": 1, "lon": 2}])


def test_fallback_never_invents_osm_identity():
    result = _fallback({"latitude": 1, "longitude": 2}, "COORDINATE_FALLBACK", "network")
    assert result["geometry_source"] == "coordinate_buffer" and result["osm_way_id"] is None


def test_parser_can_read_real_pbf_prefix():
    osmium = pytest.importorskip("osmium")
    if not DEFAULT_PBF.exists(): pytest.skip("external India PBF is not present")
    seen = []
    class StopRead(Exception): pass
    class Handler(osmium.SimpleHandler):
        def way(self, way):
            if "highway" in way.tags:
                seen.append(way.id)
                if len(seen) == 2: raise StopRead()
    try: Handler().apply_file(str(DEFAULT_PBF), locations=True)
    except StopRead: pass
    assert len(seen) == 2
