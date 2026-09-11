from p3_src.data_acquisition.phase9c_pwd_identity_resolution import resolve_identity


def test_phase9c_preserves_unresolved_identity_without_forcing_osm_matches():
    report = resolve_identity()
    assert report["input"]["records_attempted"] == 14
    assert report["observed_values"]["coordinate_available_records"] == 3
    assert report["osm_matching"]["records_eligible_for_existing_conservative_matcher"] == 0
    assert report["osm_matching"]["counts"]["NO_RELIABLE_MATCH"] == 14
    assert report["reliable_road_geometry_available"] is False


def test_phase9c_does_not_change_training_or_satellite_state():
    report = resolve_identity()
    assert report["model_b_or_satellite_changes"] is False
    assert "Do not proceed to satellite/CV" in report["conclusion"]