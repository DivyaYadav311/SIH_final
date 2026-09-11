from p3_src.historical_road_identity_audit import extract_identity, source_feature_for


def test_retained_named_road_is_explicit_but_source_availability_controls_confidence():
    result = extract_identity({"road_name": "Adivaram - Vythiri Road", "evidence_text": "Road damaged"}, False)
    assert result["road_identity_quality"] == "EXPLICIT"
    assert result["road_name_extracted"] == "Adivaram - Vythiri Road"
    assert result["identity_confidence"] == "medium"


def test_narrative_road_text_is_not_promoted_to_an_identifier():
    result = extract_identity({"road_name": "Road blocked and electric pole damaged.", "evidence_text": "Road blocked and electric pole damaged."}, False)
    assert result["road_identity_quality"] == "NARRATIVE_ONLY"
    assert result["road_name_extracted"] is None


def test_connection_text_is_preserved_as_a_route_without_inventing_ref():
    result = extract_identity({"road_name": "Lanthakhola (On Mangan to Chungthang road )", "evidence_text": "Disrupted connectivity."}, False)
    assert result["route_name_extracted"] == "Mangan to Chungthang road"
    assert result["highway_number_extracted"] is None


def test_source_feature_lookup_requires_the_exact_retained_coordinate():
    features = [{"properties": {"LATITUDE": 10, "LONGITUDE": 76, "OBJECTID": 1}, "geometry": {"coordinates": [76, 10]}}]
    assert source_feature_for({"latitude": 10, "longitude": 76}, features)["OBJECTID"] == 1
    assert source_feature_for({"latitude": 10.000001, "longitude": 76}, features) is None
