from p3_src.data_acquisition.phase9b_pwd_normalization import (
    COLUMNS,
    _deduplicate,
    _explicit_label,
    _list_records,
    build_phase9b_report,
)


def test_status_semantics_do_not_label_closure_identified():
    assert _explicit_label("Closure Identified") is None
    assert _explicit_label("Closed") is True
    assert _explicit_label("Opened") is False


def test_normalization_preserves_required_columns_and_source_identity():
    records = _list_records(
        {"data": [{
            "road_id": 19,
            "segment_id": 5731,
            "ee_office_segment_id": "<a href='eeOfficeSegmentHistory/5731'>5731</a>",
            "roadname": "Example national highway",
            "road_km_id": "10,11",
            "district_id": 4,
            "event_datetime": "2026-09-07 10:00:00",
            "status": "Closure Identified",
        }]},
        "2026-09-07T00:00:00+00:00",
    )
    assert list(records[0]) == COLUMNS
    assert records[0]["segment_id"] == "5731"
    assert records[0]["road_closed"] is None
    assert records[0]["source_record_id"]


def test_deduplication_uses_source_record_id():
    record = {"source_record_id": "same"}
    unique, removed = _deduplicate([record, record.copy()])
    assert len(unique) == 1
    assert removed == 1


def test_phase9b_report_keeps_model_b_untrained():
    report = build_phase9b_report("2026-09-07T00:00:00+00:00")
    assert report["normalization"]["normalized_record_count"] == 14
    assert report["unique_road_segments"] == 10
    assert report["model_b"]["trained"] is False
    assert report["model_b"]["disruption_probability"] is None