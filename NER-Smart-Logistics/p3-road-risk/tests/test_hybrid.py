import math

import pytest

from p3_src.hybrid import (
    compute_hybrid_disruption,
    compute_operational_disruption_score,
    compute_proximity_factor,
    compute_temporal_decay,
    generate_explanation,
    load_hybrid_config,
)


def test_prior_weights_sum_to_one():
    config = load_hybrid_config()
    assert math.isclose(sum(config["hazard_weights"].values()), 1.0)


def test_hybrid_score_and_contributions_are_mathematically_consistent():
    result = compute_operational_disruption_score({
        "flood_probability": 0.8,
        "landslide_probability": 0.4,
        "risk_probability": 0.2,
        "incident_risk": None,
    })
    assert 0 <= result["operational_disruption_score"] <= 1
    assert 0 <= result["accessibility_score"] <= 100
    assert math.isclose(sum(result["score_contributions"].values()), result["operational_disruption_score"])
    assert math.isclose(sum(result["score_weights"].values()), 1.0)


def test_missing_components_are_renormalized_and_all_missing_is_unavailable():
    result = compute_operational_disruption_score({"flood_probability": None, "landslide_probability": 0.6, "risk_probability": 0.2, "incident_risk": None})
    assert result["available_components"] == ["landslide_probability", "risk_probability"]
    assert math.isclose(sum(result["score_weights"].values()), 1.0)
    unavailable = compute_operational_disruption_score({"flood_probability": None, "landslide_probability": None, "risk_probability": None, "incident_risk": None})
    assert unavailable["operational_disruption_score"] is None
    assert unavailable["accessibility_score"] is None


def test_incident_risk_is_not_used_without_configured_prior():
    result = compute_operational_disruption_score({"flood_probability": None, "landslide_probability": None, "risk_probability": None, "incident_risk": 0.9})
    assert result["operational_disruption_score"] is None


def test_hybrid_evidence_fusion_all_factors_present():
    result = compute_hybrid_disruption({
        "road_id": "osm_way_123456",
        "timestamp": "2026-09-08T09:30:00+05:30",
        "upstream_predictions": {"flood_probability": 0.72, "landslide_probability": 0.64},
        "traffic_risk": {"risk_probability": 0.41, "incident_factor": 0.30, "congestion_factor": 0.20},
        "environment": {"rainfall_intensity_factor": 0.80, "river_level_factor": 0.65},
        "terrain": {"slope_factor": 0.75, "terrain_susceptibility_factor": 0.70},
        "road_vulnerability": {"flood_vulnerability_factor": 0.60, "road_type_vulnerability_factor": 0.70},
        "incidents": {"nearby_landslide_factor": 0.50, "nearby_flood_factor": 0.30, "nearby_accident_factor": 0.40},
    })
    assert result["road_id"] == "osm_way_123456"
    assert 0.0 <= result["disruption_probability"] <= 1.0
    assert result["operational_disruption_score"] == pytest.approx(result["disruption_probability"])
    assert result["disruption_category"] in {"LOW", "MODERATE", "HIGH", "CRITICAL"}
    assert result["evidence_confidence"] in {"LOW", "MEDIUM", "HIGH"}
    assert result["evidence"]["flood"] is True
    assert result["evidence"]["landslide"] is True
    assert result["evidence"]["traffic"] is True


def test_hybrid_evidence_fusion_only_flood_probability_available():
    result = compute_hybrid_disruption({
        "road_id": "r1",
        "timestamp": "2026-09-08T09:30:00+05:30",
        "upstream_predictions": {"flood_probability": 0.72},
    })
    assert result["components"]["flood_disruption"] is None
    assert result["components"]["landslide_disruption"] is None
    assert result["disruption_probability"] == pytest.approx(0.0, abs=1e-9)


def test_hybrid_evidence_fusion_only_landslide_probability_available():
    result = compute_hybrid_disruption({
        "road_id": "r2",
        "timestamp": "2026-09-08T09:30:00+05:30",
        "upstream_predictions": {"landslide_probability": 0.68},
    })
    assert result["components"]["landslide_disruption"] is None
    assert result["components"]["flood_disruption"] is None
    assert result["disruption_probability"] == pytest.approx(0.0, abs=1e-9)


def test_missing_environmental_factors_are_renormalized():
    result = compute_hybrid_disruption({
        "road_id": "r3",
        "timestamp": "2026-09-08T09:30:00+05:30",
        "upstream_predictions": {"flood_probability": 0.72, "landslide_probability": 0.50},
        "environment": {"rainfall_intensity_factor": 0.8, "river_level_factor": None},
        "terrain": {"slope_factor": 0.4, "terrain_susceptibility_factor": 0.6},
        "road_vulnerability": {"flood_vulnerability_factor": 0.6},
        "incidents": {"nearby_landslide_factor": 0.4},
        "traffic_risk": {"risk_probability": 0.3},
    })
    expected_flood_environment = (0.40 * 0.8 + 0.20 * 0.6) / (0.40 + 0.20)
    expected_flood_disruption = 0.72 * expected_flood_environment
    assert result["components"]["flood_disruption"] == pytest.approx(expected_flood_disruption, abs=1e-9)
    assert result["evidence"]["river"] is False


def test_all_optional_environmental_factors_null():
    result = compute_hybrid_disruption({
        "road_id": "r4",
        "timestamp": "2026-09-08T09:30:00+05:30",
        "upstream_predictions": {"flood_probability": 0.72},
        "environment": {"rainfall_intensity_factor": None, "river_level_factor": None},
        "terrain": {"slope_factor": None, "terrain_susceptibility_factor": None},
        "road_vulnerability": {"flood_vulnerability_factor": None},
        "incidents": {"nearby_landslide_factor": None},
        "traffic_risk": {"risk_probability": None, "incident_factor": None, "congestion_factor": None},
    })
    assert result["evidence"]["rainfall"] is False
    assert result["disruption_probability"] == pytest.approx(0.0, abs=1e-9)


def test_synergy_bonus_activates_for_high_flood_and_landslide():
    result = compute_hybrid_disruption({
        "road_id": "r5",
        "timestamp": "2026-09-08T09:30:00+05:30",
        "upstream_predictions": {"flood_probability": 0.90, "landslide_probability": 0.90},
    })
    assert result["synergy_bonus"] > 0.0
    assert result["final_disruption"] == pytest.approx(result["disruption_probability"])
    assert result["synergy_bonus"] == pytest.approx(0.08, abs=1e-9)


def test_synergy_bonus_is_zero_below_threshold():
    result = compute_hybrid_disruption({
        "road_id": "r6",
        "timestamp": "2026-09-08T09:30:00+05:30",
        "upstream_predictions": {"flood_probability": 0.40, "landslide_probability": 0.40},
    })
    assert result["synergy_bonus"] == pytest.approx(0.0, abs=1e-9)


def test_output_always_stays_in_unit_interval():
    payloads = [
        {"upstream_predictions": {"flood_probability": 0.72, "landslide_probability": 0.64}, "traffic_risk": {"risk_probability": 0.41}},
        {"upstream_predictions": {"flood_probability": 1.0, "landslide_probability": 1.0}, "traffic_risk": {"risk_probability": 1.0}},
        {"upstream_predictions": {"flood_probability": 0.0, "landslide_probability": 0.0}, "traffic_risk": {"risk_probability": 0.0}},
    ]
    for payload in payloads:
        result = compute_hybrid_disruption(payload)
        assert 0.0 <= result["disruption_probability"] <= 1.0
        assert 0.0 <= result["operational_disruption_score"] <= 1.0


def test_disruption_category_thresholds_are_correct():
    cases = [
        ({"risk_probability": 0.20}, "LOW"),
        ({"risk_probability": 0.30}, "MODERATE"),
        ({"risk_probability": 0.60}, "HIGH"),
        ({"risk_probability": 0.80}, "CRITICAL"),
    ]
    for probabilities, expected in cases:
        result = compute_hybrid_disruption({"traffic_risk": probabilities})
        assert result["disruption_category"] == expected


def test_evidence_completeness_is_correctly_calculated():
    complete = compute_hybrid_disruption({
        "road_id": "r7",
        "timestamp": "2026-09-08T09:30:00+05:30",
        "upstream_predictions": {"flood_probability": 0.72, "landslide_probability": 0.64},
        "traffic_risk": {"risk_probability": 0.41, "incident_factor": 0.30, "congestion_factor": 0.20},
        "environment": {"rainfall_intensity_factor": 0.80, "river_level_factor": 0.65},
        "terrain": {"slope_factor": 0.75, "terrain_susceptibility_factor": 0.70},
        "road_vulnerability": {"flood_vulnerability_factor": 0.60},
        "incidents": {"nearby_landslide_factor": 0.50, "nearby_accident_factor": 0.40},
    })
    assert 0.0 <= complete["evidence_completeness"] <= 1.0
    assert complete["evidence_completeness"] >= 0.80

    partial = compute_hybrid_disruption({
        "road_id": "r8",
        "timestamp": "2026-09-08T09:30:00+05:30",
        "upstream_predictions": {"flood_probability": 0.72},
    })
    assert partial["evidence_completeness"] < complete["evidence_completeness"]


def test_fallback_explanation_works_when_genai_unavailable():
    result = compute_hybrid_disruption({
        "road_id": "r9",
        "timestamp": "2026-09-08T09:30:00+05:30",
        "upstream_predictions": {"flood_probability": 0.72, "landslide_probability": 0.64},
    })
    explanation = generate_explanation(result)
    assert "disruption likelihood score is" in explanation.lower()
    assert "primary" in explanation.lower() or "secondary" in explanation.lower()


def test_genai_cannot_change_numerical_score():
    result = compute_hybrid_disruption({
        "road_id": "r10",
        "timestamp": "2026-09-08T09:30:00+05:30",
        "upstream_predictions": {"flood_probability": 0.72, "landslide_probability": 0.64},
    })
    score_before = result["disruption_probability"]
    _ = generate_explanation(result)
    assert result["disruption_probability"] == pytest.approx(score_before, abs=1e-9)


def test_probabilities_outside_unit_interval_are_rejected():
    with pytest.raises(ValueError):
        compute_hybrid_disruption({"upstream_predictions": {"flood_probability": 1.2}})
    with pytest.raises(ValueError):
        compute_hybrid_disruption({"upstream_predictions": {"landslide_probability": -0.1}})


def test_existing_accident_model_behavior_remains_unchanged():
    from p3_src.ml_pipeline.inference import predict_severity_risk

    values = {
        "road_id": "ROAD-ML-001",
        "latitude": 19.076,
        "longitude": 72.878,
        "timestamp": "2026-09-05T12:00:00Z",
        "lanes": 2,
        "traffic_signal": 1,
        "temperature": 30,
        "vehicles_involved": 2,
        "casualties": 1,
        "is_peak_hour": 0,
        "road_type": "urban",
        "weather": "clear",
        "visibility": "high",
        "traffic_density": "low",
        "cause": "weather",
        "city": "mumbai",
        "state": "maharashtra",
        "flood_probability": 0.7,
        "landslide_probability": 0.2,
    }
    result = predict_severity_risk(values)
    assert 0.0 <= result["risk_probability"] <= 1.0
    assert "road_disruption_model_status" in result


def test_spatial_and_temporal_decay_are_bounded_and_deterministic():
    assert compute_proximity_factor(0.0, 5.0) == pytest.approx(1.0)
    assert compute_proximity_factor(5.0, 5.0) == pytest.approx(math.exp(-1.0))
    assert compute_temporal_decay("2026-09-08T09:30:00+00:00", "2026-09-08T09:30:00+00:00", 24) == pytest.approx(1.0)
    assert compute_temporal_decay("2026-09-08T08:30:00+00:00", "2026-09-08T09:30:00+00:00", 24) == pytest.approx(math.exp(-1 / 24))


def test_future_incident_is_rejected_before_scoring():
    with pytest.raises(ValueError, match="future event"):
        compute_hybrid_disruption({
            "timestamp": "2026-09-08T09:30:00+00:00",
            "traffic_risk": {"risk_probability": 0.4, "nearby_accident_factor": 0.8, "nearby_accident_factor_metadata": {"event_timestamp": "2026-09-08T10:30:00+00:00"}},
        })


def test_nearby_flood_evidence_is_used_with_decay():
    result = compute_hybrid_disruption({
        "timestamp": "2026-09-08T09:30:00+00:00",
        "upstream_predictions": {"flood_probability": 0.8},
        "environment": {"rainfall_intensity_factor": 0.5},
        "incidents": {"nearby_flood_factor": 0.9, "nearby_flood_factor_metadata": {"distance_km": 0.0, "event_timestamp": "2026-09-08T08:30:00+00:00"}},
    })
    assert result["factors"]["nearby_flood_factor"] == pytest.approx(0.9 * math.exp(-1 / 24))
    assert result["evidence"]["spatial_context"] is True
    assert result["evidence"]["temporal_context"] is True


def test_top_level_components_renormalize_when_flood_is_unavailable():
    result = compute_hybrid_disruption({
        "upstream_predictions": {"landslide_probability": 0.8},
        "traffic_risk": {"risk_probability": 0.4},
        "terrain": {"slope_factor": 0.5},
    })
    assert result["score_weights"] == {"landslide": pytest.approx(2 / 3), "traffic": pytest.approx(1 / 3)}
    assert result["disruption_probability"] == pytest.approx(0.4 * 2 / 3 + 0.4 / 3)


def test_vulnerability_modifier_is_bounded_and_contributions_reconcile():
    result = compute_hybrid_disruption({
        "upstream_predictions": {"flood_probability": 0.8},
        "environment": {"rainfall_intensity_factor": 0.8},
        "road_vulnerability": {"road_vulnerability_factor": 1.0},
    })
    assert result["components"]["road_vulnerability_modifier"] == pytest.approx(1.1)
    assert sum(result["score_contributions"].values()) == pytest.approx(result["operational_disruption_score"])


def test_invalid_nested_input_is_rejected():
    with pytest.raises(ValueError, match="traffic_risk must be an object"):
        compute_hybrid_disruption({"traffic_risk": []})


def test_same_payload_is_exactly_deterministic():
    payload = {"upstream_predictions": {"flood_probability": 0.8}, "environment": {"rainfall_intensity_factor": 0.7}}
    assert compute_hybrid_disruption(payload) == compute_hybrid_disruption(payload)
