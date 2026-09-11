from pathlib import Path

import pandas as pd


def test_build_incident_dataset_records_no_real_label_evidence(tmp_path):
    from p3_src.data_pipeline.build_incident_dataset import build_incident_dataset

    summary = build_incident_dataset(project_root=tmp_path)

    assert summary["reports_discovered"] >= 0
    assert summary["reports_downloaded"] >= 0
    assert summary["road_impact_candidates"] == 0
    assert summary["high_confidence_records"] == 0
    assert summary["medium_confidence_records"] == 0
    assert summary["low_confidence_records"] == 0
    assert summary["records_with_coordinates"] == 0
    assert summary["osm_road_matches"] == 0
    assert summary["ambiguous_matches"] == 0
    assert summary["unmatched_records"] == 0
    assert summary["real_road_impact_labels_available"] is False

    evidence_path = tmp_path / "data" / "processed" / "road_impact_evidence.csv"
    labels_path = tmp_path / "data" / "processed" / "road_impact_labels.csv"
    review_path = tmp_path / "data" / "processed" / "road_impact_review.csv"

    assert evidence_path.exists()
    assert labels_path.exists()
    assert review_path.exists()

    evidence = pd.read_csv(evidence_path)
    labels = pd.read_csv(labels_path)
    review = pd.read_csv(review_path)

    assert list(evidence.columns) == [
        "incident_id",
        "source",
        "source_url",
        "source_file",
        "report_title",
        "report_date",
        "event_date",
        "state",
        "district",
        "location_text",
        "road_name",
        "road_reference",
        "incident_type",
        "impact_type",
        "original_text",
        "extraction_method",
        "evidence_confidence",
    ]
    assert list(labels.columns) == [
        "incident_id",
        "osm_road_id",
        "event_date",
        "road_disrupted",
        "label_confidence",
        "source",
        "source_url",
        "source_file",
        "source_page",
        "original_text",
    ]
    assert len(evidence.index) == 0
    assert len(labels.index) == 0
    assert len(review.index) == 0


def test_build_gdelt_queries_are_explicit_and_long_enough_for_public_api():
    from p3_src.data_pipeline.gdelt.query_builder import build_gdelt_queries

    queries = build_gdelt_queries(states=["Assam"])

    assert len(queries) >= 1
    for entry in queries:
        assert entry["state"] == "Assam"
        query = entry["query"]
        assert '"Assam"' in query
        assert len(query.split()) >= 8
        assert '"road' in query or '"highway' in query or '"bridge' in query
        assert 'blocked' in query or 'closure' in query or 'cut off' in query or 'washed away' in query or 'damaged' in query
        assert 'flood' in query or 'landslide' in query or 'heavy rain' in query or 'flash flood' in query
