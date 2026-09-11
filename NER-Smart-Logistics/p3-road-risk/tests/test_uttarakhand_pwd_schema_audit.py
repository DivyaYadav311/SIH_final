from p3_src.data_acquisition.uttarakhand_pwd_schema_audit import (
    audit,
    field_presence,
    parse_history_tables,
    status_semantics,
    write_reports,
)


LIST_PAYLOAD = {
    "draw": 1,
    "recordsTotal": 2,
    "recordsFiltered": 2,
    "data": [
        {
            "DT_RowIndex": 1,
            "roadname": '<a href="https://mis.pwduk.in/pwd/eeOfficeSegmentHistory/1">Example Highway</a>',
            "ee_office_segment_id": '<a href="https://mis.pwduk.in/pwd/eeOfficeSegmentHistory/1">1</a>',
            "road_km_id": "10,11",
            "event_datetime": "2026-09-01 08:00:00",
            "status": "Closure Identified",
            "created_by": "Officer",
            "segment_id": 1,
            "road_id": 1,
            "district_id": 4,
            "block_id": 1,
            "constituency_id": 1,
            "road_type_id": 1,
            "tc_date": "2026-09-01 08:00:00",
            "initial_cost": 1.0,
            "restoration_cost": 1.0,
        }
    ],
}

HISTORY_HTML = """
<table>
<tr><th>#</th><th>KM</th><th>Closed On</th><th>Opened On</th><th>Open Type</th><th>Damage Type</th><th>Remark</th><th>lat</th><th>lng</th><th>ID</th></tr>
<tr><td>1</td><td>10</td><td>2026-09-01 07:00:00</td><td>2026-09-01 09:00:00</td><td>Opened</td><td>Slip/ Landslide</td><td>debris</td><td>30.1</td><td>78.1</td><td>99</td></tr>
</table>
"""


def test_parser_keeps_history_column_names():
    rows = parse_history_tables(HISTORY_HTML)
    assert len(rows) == 1
    assert rows[0]["KM"] == "10"
    assert rows[0]["Closed On"] == "2026-09-01 07:00:00"
    assert rows[0]["lat"] == "30.1"


def test_requested_fields_are_not_invented():
    presence = field_presence(
        ["roadname", "ee_office_segment_id", "road_km_id", "event_datetime", "status", "district_id"],
        ["KM", "Closed On", "Opened On", "Open Type", "Damage Type", "Remark", "lat", "lng", "ID"],
    )
    assert presence["road_name"]["source_field_names"] == ["roadname"]
    assert presence["highway_number"]["present"] is False
    assert presence["road_number"]["present"] is False
    assert presence["latitude"]["source_field_names"] == ["lat"]
    assert presence["source_record_id"]["source_field_names"] == ["ID"]


def test_status_semantics_are_unknown_without_a_dictionary():
    rows = status_semantics(["Closure Identified", "Opened"])
    assert all("UNKNOWN" in item["semantics"] for item in rows)


def test_audit_uses_sample_counts_and_refuses_osm_guessing_without_coords():
    result = audit({"draw": 1, "recordsTotal": 1, "data": [{"roadname": "A", "status": "Closure Identified"}]}, "<table></table>")
    assert result["sample"]["list_record_count"] == 1
    assert result["road_identity_feasibility"]["can_map_to_unique_osm_road_without_guessing"] is False
    assert result["road_identity_feasibility"]["large_scale_osm_matching_run"] is False


def test_saved_pwd_sample_reports_without_training_side_effects():
    written = write_reports(retrieval_timestamp="2026-09-07T13:15:00+00:00")
    assert written["audit"]["sample"]["list_record_count"] == 10
    assert "Closure Identified" in written["audit"]["status_values"]["list_json_status"]
    assert written["phase9a"]["data_acquired"] is True
    assert written["phase9a"]["not_done"]
    assert "Model B training" in written["phase9a"]["not_done"]
    assert written["audit"]["road_identity_feasibility"]["history_page_has_lat_lng"] is True
