import pandas as pd

from p3_src.data_acquisition import collect_closure_data as closure


def test_only_explicit_road_blockage_gets_positive_label():
    assert closure.evidence_sentence("A landslide occurred near the road.", closure.CLOSED_PATTERNS) is None
    assert closure.evidence_sentence("The road was blocked by debris.", closure.CLOSED_PATTERNS)
    assert closure.evidence_sentence("The road reopened to traffic.", closure.OPEN_PATTERNS)
    assert closure.evidence_sentence("Traffic was restored on NH-5.", closure.OPEN_PATTERNS)


def test_unknown_is_not_converted_to_negative():
    records = closure.deduplicate([
        {
            "source_id": "source", "source_record_id": "1", "road_name": "Hill Road",
            "state": "Kerala", "district": "X", "latitude": 11.0, "longitude": 75.0,
            "closure_status": "unknown", "road_closed": None, "evidence_text": "Road damaged",
            "source_url": "unknown",
        }
    ])
    assert len(records) == 1
    assert records[0]["road_closed"] is None


def test_duplicate_reopening_evidence_is_deduplicated_without_losing_negative_label():
    base = {
        "source_id": "source", "source_record_id": "1", "road_name": "NH-5",
        "state": "Himachal Pradesh", "district": "Shimla", "latitude": 31.1,
        "longitude": 77.1, "closure_status": "open", "road_closed": 0,
        "evidence_text": "Traffic was restored on NH-5.", "source_url": "u",
    }
    records = closure.deduplicate([base, dict(base, source_record_id="2")])
    assert len(records) == 1
    assert records[0]["road_closed"] == 0
    assert records[0]["source_count"] == 1


def test_status_sequence_keeps_positive_and_negative_observations_separate():
    rows = pd.DataFrame([
        {"event_timestamp": "2023-07-15", "road_closed": 1},
        {"event_timestamp": "2023-07-17", "road_closed": 0},
    ]).sort_values("event_timestamp")
    assert rows.iloc[0].road_closed == 1
    assert rows.iloc[1].road_closed == 0


def test_event_schema_keeps_missing_timestamp_and_osm_id_null():
    assert "event_timestamp" in closure.EVENT_COLUMNS
    assert "osm_road_id" in closure.EVENT_COLUMNS
    assert closure.normalize_road("National Highway 5") == "nh-5"


def test_explicit_narrative_date_is_event_date_not_exact_time():
    value = closure.extract_event_date({"ABSTRACT": "On 14th June 2018 a debris flow occurred."})
    assert value == ("2018-06-14", "event_date", "high", "ABSTRACT")
    assert closure.extract_event_date({"REPORT": "KER_2007_0001.pdf"})[0] is None


def test_collector_outputs_real_counts_and_no_model_without_open_labels(tmp_path, monkeypatch):
    monkeypatch.setattr(closure, "SOURCE_GEOJSON", tmp_path / "missing.geojson")
    monkeypatch.setattr(closure, "RAW_ROOT", tmp_path / "raw")
    monkeypatch.setattr(closure, "CACHE_ROOT", tmp_path / "raw" / "cache")
    monkeypatch.setattr(closure, "MANIFEST_ROOT", tmp_path / "raw" / "source_manifests")
    monkeypatch.setattr(closure, "PROCESSED_ROOT", tmp_path / "processed")
    monkeypatch.setattr(closure, "REPORT_ROOT", tmp_path / "reports")
    result = closure.collect(force=True)
    assert result["source_records_examined"] == 0
    assert result["model_trained"] is False
    assert result["disruption_probability_available"] is False
    assert (tmp_path / "processed" / "road_closure_events.parquet").exists()
