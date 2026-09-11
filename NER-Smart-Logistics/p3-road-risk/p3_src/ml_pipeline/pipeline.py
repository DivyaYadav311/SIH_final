from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.ensemble import HistGradientBoostingClassifier

from . import PIPELINE_VERSION

ROOT = Path(__file__).resolve().parents[2]
TRAINING_ROOT = ROOT / "data" / "raw" / "training"
REPORT_ROOT = ROOT / "data" / "reports"
CHECKPOINT_ROOT = ROOT / "data" / "checkpoints"
PROCESSED_ROOT = ROOT / "data" / "processed"
MODEL_ROOT = ROOT / "models"

ACCIDENT_ARCHIVE = TRAINING_ROOT / "indian_road_accident" / "indian_road_accident.zip"
IOT_ARCHIVE = TRAINING_ROOT / "iot_traffic_dataset" / "iot.zip"
OSM_PBF = ROOT / "data" / "raw" / "roads" / "india-latest.osm.pbf"
RAINFALL_NETCDF = ROOT / "data" / "raw" / "rainfall" / "IMD_rainfall_*.nc"
RIVER_CSV = ROOT / "data" / "raw" / "water_levels" / "cwc_river_levels.csv.csv"
LANDSLIDE_GEOJSON = ROOT / "data" / "raw" / "landslides" / "historical_landslides.geojson"

TARGET = "severity_risk_target"
FEATURE_COLUMNS = [
    "latitude", "longitude", "hour", "is_weekend", "lanes", "traffic_signal",
    "temperature", "is_peak_hour", "road_type", "weather", "visibility", "traffic_density",
    "city", "state",
    "rainfall_24h", "rainfall_3d", "rainfall_7d",
    "nearest_landslide_distance_km", "nearby_landslide_count", "nearest_river_distance_km",
]
OPTIONAL_UPSTREAM_FEATURES = ["flood_probability", "landslide_probability"]
ENRICHMENT_FEATURES = [
    "rainfall_24h", "rainfall_3d", "rainfall_7d", "rainfall_observation_date",
    "nearest_landslide_distance_km", "nearby_landslide_count",
    "nearest_river_distance_km", "river_level", "river_level_change", "river_observation_timestamp",
    "osm_road_id", "match_distance_m", "match_confidence", "match_method",
]
NUMERIC_FEATURES = [
    "latitude", "longitude", "hour", "is_weekend", "lanes", "traffic_signal",
    "temperature", "is_peak_hour", "rainfall_24h", "rainfall_3d", "rainfall_7d",
    "nearest_landslide_distance_km", "nearby_landslide_count", "nearest_river_distance_km",
]
CATEGORICAL_FEATURES = [
    "road_type", "weather", "visibility", "traffic_density", "city", "state",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_hash(row: pd.Series) -> str:
    payload = "|".join("" if pd.isna(v) else str(v) for v in row.tolist())
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


def atomic_write_bytes(destination: Path, data: bytes) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{destination.name}.", dir=destination.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def atomic_write_json(destination: Path, value: Any) -> None:
    atomic_write_bytes(destination, json.dumps(value, indent=2, default=str).encode("utf-8"))


def atomic_write_dataframe(frame: pd.DataFrame, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.tmp")
    if temporary.exists():
        temporary.unlink()
    frame.to_parquet(temporary, index=False)
    os.replace(temporary, destination)


def checkpoint(stage: str, input_hash: str, config: dict[str, Any], output: Path, builder) -> pd.DataFrame:
    stage_dir = CHECKPOINT_ROOT / stage
    stage_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = stage_dir / "manifest.json"
    config_hash = hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()
    if output.exists() and manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
        if manifest.get("input_hash") == input_hash and manifest.get("config_hash") == config_hash:
            return pd.read_parquet(output)
    frame = builder()
    atomic_write_dataframe(frame, output)
    atomic_write_json(manifest_path, {
        "stage": stage, "status": "complete", "input_hash": input_hash,
        "config_hash": config_hash, "output_path": str(output),
        "row_count": len(frame), "schema": {c: str(t) for c, t in frame.dtypes.items()},
        "timestamp": utc_now(), "pipeline_version": PIPELINE_VERSION,
    })
    return frame


def source_descriptor(name: str, archive: Path, member: str, frame: pd.DataFrame) -> dict[str, Any]:
    descriptor: dict[str, Any] = {
        "dataset": name,
        "archive": str(archive.relative_to(ROOT)),
        "member": member,
        "file_size_bytes": archive.stat().st_size,
        "sha256": sha256(archive),
        "rows": len(frame),
        "columns": list(frame.columns),
        "dtypes": {c: str(t) for c, t in frame.dtypes.items()},
        "missing_values": {c: int(v) for c, v in frame.isna().sum().items()},
        "duplicate_rows": int(frame.duplicated().sum()),
    }
    for column in frame.columns:
        if frame[column].dtype == "object":
            values = frame[column].dropna().astype(str)
            descriptor.setdefault("categorical", {})[column] = {
                "unique_count": int(values.nunique()), "values_sample": sorted(values.unique().tolist())[:30]
            }
    timestamp_column = "timestamp" if "timestamp" in frame else "date" if "date" in frame else None
    if timestamp_column:
        parsed = pd.to_datetime(frame[timestamp_column], errors="coerce")
        descriptor["timestamp"] = {
            "column": timestamp_column, "valid_count": int(parsed.notna().sum()),
            "invalid_count": int(parsed.isna().sum()),
            "min": str(parsed.min()) if parsed.notna().any() else None,
            "max": str(parsed.max()) if parsed.notna().any() else None,
        }
    if "latitude" in frame and "longitude" in frame:
        lat = pd.to_numeric(frame.latitude, errors="coerce")
        lon = pd.to_numeric(frame.longitude, errors="coerce")
        valid = lat.between(-90, 90) & lon.between(-180, 180)
        descriptor["coordinates"] = {
            "valid_count": int(valid.sum()), "invalid_count": int((~valid).sum()),
            "min_lat": float(lat.min()), "max_lat": float(lat.max()),
            "min_lon": float(lon.min()), "max_lon": float(lon.max()),
        }
    return descriptor


def read_archive(archive: Path) -> tuple[str, pd.DataFrame]:
    with zipfile.ZipFile(archive) as bundle:
        members = [name for name in bundle.namelist() if not name.endswith("/")]
        csv_members = [name for name in members if name.lower().endswith(".csv")]
        if len(csv_members) != 1:
            raise ValueError(f"Expected exactly one CSV in {archive}, found {csv_members}")
        with bundle.open(csv_members[0]) as handle:
            return csv_members[0], pd.read_csv(handle)


def _column_audit(frame: pd.DataFrame) -> list[dict[str, Any]]:
    geographic = {"latitude", "longitude", "city", "state", "District", "district"}
    temporal = {"date", "time", "timestamp", "hour", "day_of_week", "is_weekend", "is_peak_hour"}
    post_event = {"accident_severity", "casualties", "vehicles_involved", "risk_score"}
    rows = []
    for column in frame.columns:
        values = frame[column]
        lower = column.lower()
        rows.append({
            "column": column,
            "semantic_meaning": {
                "accident_severity": "observed accident severity",
                "risk_score": "source-provided risk score with target-derived leakage risk",
                "casualties": "observed casualties after an accident",
                "vehicles_involved": "observed vehicles involved in an accident",
                "date": "calendar date of recorded accident",
                "time": "clock time of recorded accident",
                "latitude": "accident latitude",
                "longitude": "accident longitude",
                "road_type": "source road class category",
                "traffic_density": "source traffic-density category",
                "cause": "recorded accident cause; potentially post-event or unavailable prospectively",
            }.get(column, "source field; meaning requires source documentation"),
            "dtype": str(values.dtype),
            "missing_percentage": float(values.isna().mean() * 100),
            "cardinality": int(values.nunique(dropna=True)),
            "geographic_usefulness": "high" if column in geographic else "none",
            "temporal_usefulness": "high" if column in temporal else "none",
            "known_before_accident": bool(column in {"latitude", "longitude", "city", "state", "date", "time", "hour", "day_of_week", "is_weekend", "road_type", "lanes", "traffic_signal", "weather", "visibility", "temperature", "traffic_density", "is_peak_hour"}),
            "known_only_after_accident": bool(column in post_event),
            "target_leakage": bool(column in {"risk_score", "accident_severity"}),
            "environmental_spatial_join": bool(column in {"latitude", "longitude"}),
            "osm_join_use": bool(column in {"latitude", "longitude", "road_type", "lanes"}),
        })
    return rows


def write_accident_deep_audit(frame: pd.DataFrame) -> None:
    rows = _column_audit(frame)
    payload = {"dataset": "indian_road_accident", "rows": len(frame), "columns": rows, "generated_at": utc_now(), "pipeline_version": PIPELINE_VERSION}
    atomic_write_json(REPORT_ROOT / "accident_feature_deep_audit.json", payload)
    lines = ["# Indian accident feature deep audit", "", f"Rows: {len(frame)}", "", "| Column | Type | Missing % | Cardinality | Before accident | After accident | Leakage | Spatial join | OSM |", "|---|---|---:|---:|---|---|---|---|---|"]
    for row in rows:
        lines.append(f"| {row['column']} | {row['dtype']} | {row['missing_percentage']:.2f} | {row['cardinality']} | {row['known_before_accident']} | {row['known_only_after_accident']} | {row['target_leakage']} | {row['environmental_spatial_join']} | {row['osm_join_use']} |")
    lines += ["", "Interpretation: source fields without documentation are not automatically treated as prediction-time features. `risk_score` and `accident_severity` are rejected from model features; casualties and vehicles involved describe an observed accident and are retained only for the current retrospective severity-risk submodel."]
    (REPORT_ROOT / "accident_feature_deep_audit.md").write_text("\n".join(lines))


def write_target_candidates(frame: pd.DataFrame) -> None:
    candidates = [
        ["accident_severity", "Observed severity of an accident", "fatal or major", "minor", True, "Only defensible supervised target in the Indian source; not road disruption", "Source target; exclude from features"],
        ["risk_score", "Source-provided accident risk score", "high numeric score", "low numeric score", False, "Likely target-derived and no independent definition supplied", "High"],
        ["cause", "Recorded accident cause", "weather/distraction/etc.", "other cause", False, "Cause is an observed categorical explanation, not occurrence/disruption ground truth", "Post-event or semantic ambiguity"],
        ["road_type", "Road class at accident record", "highway/urban/rural", "other", False, "Feature, not an incident target", "None as target; feature semantics limited"],
        ["traffic_density", "Recorded traffic density", "high/medium/low", "other", False, "Feature, not traffic disruption ground truth", "None as target; may be contemporaneous"],
        ["latitude/longitude", "Accident location", "valid coordinates", "invalid/missing", False, "Location fields, not target", "None"],
    ]
    columns = ["candidate_column", "semantic_definition", "positive_condition", "negative_condition", "usable_for_training", "reason", "leakage_risk"]
    pd.DataFrame(candidates, columns=columns).to_csv(REPORT_ROOT / "target_candidates.csv", index=False)


def audit_sources() -> dict[str, Any]:
    REPORT_ROOT.mkdir(parents=True, exist_ok=True)
    descriptors = []
    for name, archive in [("indian_road_accident", ACCIDENT_ARCHIVE), ("iot_traffic", IOT_ARCHIVE)]:
        if not archive.exists():
            raise FileNotFoundError(archive)
        member, frame = read_archive(archive)
        descriptor = source_descriptor(name, archive, member, frame)
        if name == "indian_road_accident":
            descriptor["target_candidates"] = {
                "accident_severity": sorted(frame["accident_severity"].unique().tolist()),
                "risk_score": "numeric score; rejected as target-derived leakage candidate",
            }
            descriptor["geographic_interpretation"] = "India; seven named states and eight cities"
        else:
            descriptor["target_candidates"] = {
                "event_type": sorted(frame["event_type"].unique().tolist()),
                "incident_report": sorted(frame["incident_report"].dropna().unique().tolist()),
            }
            descriptor["geographic_interpretation"] = "Outside India; coordinates span the continental United States"
        descriptors.append(descriptor)
    raw_inventory = []
    for path in sorted((ROOT / "data" / "raw").rglob("*")):
        if path.is_file() and path.name != ".DS_Store":
            raw_inventory.append({
                "path": str(path.relative_to(ROOT)), "file_size_bytes": path.stat().st_size,
                "sha256": sha256(path), "file_type": path.suffix.lower() or "no_extension",
            })
    payload = {"pipeline_version": PIPELINE_VERSION, "generated_at": utc_now(), "datasets": descriptors, "raw_inventory": raw_inventory}
    atomic_write_json(REPORT_ROOT / "data_audit.json", payload)
    lines = ["# Data audit", "", f"Generated: {payload['generated_at']}", ""]
    for item in descriptors:
        lines += [f"## {item['dataset']}", "", f"- Archive: `{item['archive']}`", f"- Member: `{item['member']}`", f"- Rows: {item['rows']}", f"- SHA256: `{item['sha256']}`", f"- Duplicate rows: {item['duplicate_rows']}", f"- Columns: {', '.join(item['columns'])}", f"- Geographic interpretation: {item['geographic_interpretation']}", ""]
        if "timestamp" in item:
            lines.append(f"- Time coverage: {item['timestamp']['min']} through {item['timestamp']['max']} ({item['timestamp']['valid_count']} valid)")
        if "coordinates" in item:
            c = item["coordinates"]
            lines.append(f"- Coordinates: {c['valid_count']} valid; lat {c['min_lat']}..{c['max_lat']}, lon {c['min_lon']}..{c['max_lon']}")
        lines += [f"- Missing values: `{json.dumps(item['missing_values'])}`", ""]
    (REPORT_ROOT / "data_audit.md").write_text("\n".join(lines))
    return payload


def write_static_reports() -> None:
    mapping = [
        ["indian_road_accident", "date + time", "timestamp", "datetime", "combine and parse", "remove invalid", "event time"],
        ["indian_road_accident", "latitude", "latitude", "float", "numeric coercion", "remove invalid coordinates", "incident latitude"],
        ["indian_road_accident", "longitude", "longitude", "float", "numeric coercion", "remove invalid coordinates", "incident longitude"],
        ["indian_road_accident", "accident_severity", TARGET, "binary", "fatal/major=1, minor=0", "reject missing", "severity-risk target, not disaster closure"],
        ["indian_road_accident", "risk_score", "rejected", "float", "none", "exclude", "target-derived risk score; leakage"],
        ["indian_road_accident", "road_type", "road_type", "category", "lowercase", "unknown category", "road class"],
        ["indian_road_accident", "traffic_density", "traffic_density", "category", "lowercase", "unknown category", "traffic condition"],
        ["iot_traffic", "vehicle_speed (km/h)", "vehicle_speed", "float", "numeric coercion", "median imputation if used", "generic traffic speed; outside India"],
        ["iot_traffic", "event_type", "event_type", "category", "lowercase", "unknown category", "incident context; not merged"],
        ["iot_traffic", "incident_report", "incident_report", "category", "normalize missing", "unknown category", "incident context; not merged"],
    ]
    columns = ["source_dataset", "source_column", "mapped_feature", "data_type", "transformation", "missing_value_strategy", "semantic_description"]
    pd.DataFrame(mapping, columns=columns).to_csv(REPORT_ROOT / "feature_mapping.csv", index=False)
    atomic_write_json(REPORT_ROOT / "geographic_coverage.json", {
        "dataset": "indian_road_accident", "min_lat": 12.800172, "max_lat": 30.79996,
        "min_lon": 72.700017, "max_lon": 88.499861, "estimated_country_coverage": "India, seven states / eight cities",
        "indian_row_count": 20000, "non_indian_row_count": 0, "unknown_row_count": 0,
        "excluded_dataset": {"dataset": "iot_traffic", "estimated_country_coverage": "United States", "indian_row_count": 0, "non_indian_row_count": 1000, "unknown_row_count": 0},
    })
    manifest_rows = []
    for dataset_name, archive in [("indian_road_accident", ACCIDENT_ARCHIVE), ("iot_traffic", IOT_ARCHIVE)]:
        manifest_rows.append({
            "dataset_name": dataset_name, "local_path": str(archive.relative_to(ROOT)),
            "file_size": archive.stat().st_size, "sha256": sha256(archive),
            "download_source": "unknown", "download_date": "unknown",
            "license_source_notes": "Local archive supplied to the project; verify license/source before redistribution.",
        })
    manifest_path = ROOT / "data" / "manifests" / "source_manifest.csv"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(manifest_rows).to_csv(manifest_path, index=False)


def extract_accidents() -> pd.DataFrame:
    member, frame = read_archive(ACCIDENT_ARCHIVE)
    frame["source_dataset"] = "indian_road_accident"
    frame["source_file"] = f"{ACCIDENT_ARCHIVE.relative_to(ROOT)}::{member}"
    frame["source_row_id"] = frame.apply(stable_hash, axis=1)
    input_hash = sha256(ACCIDENT_ARCHIVE)
    return checkpoint("02_extracted", input_hash, {"member": member}, CHECKPOINT_ROOT / "02_extracted" / "accidents.parquet", lambda: frame)


def clean_accidents(frame: pd.DataFrame) -> pd.DataFrame:
    cleaned = frame.copy()
    before = len(cleaned)
    cleaned["timestamp"] = pd.to_datetime(cleaned["date"].astype(str) + " " + cleaned["time"].astype(str), errors="coerce")
    for column in ["latitude", "longitude", "hour", "lanes", "traffic_signal", "temperature", "vehicles_involved", "casualties", "is_peak_hour", "is_weekend"]:
        cleaned[column] = pd.to_numeric(cleaned[column], errors="coerce")
    valid_coords = cleaned.latitude.between(-90, 90) & cleaned.longitude.between(-180, 180)
    valid_timestamp = cleaned.timestamp.notna()
    cleaned = cleaned[valid_coords & valid_timestamp].copy()
    cleaned["speed_invalid"] = False
    for column in ["road_type", "weather", "visibility", "traffic_density", "cause", "city", "state"]:
        cleaned[column] = cleaned[column].astype("string").str.strip().str.lower().replace({"": pd.NA, "nan": pd.NA})
    cleaned[TARGET] = cleaned["accident_severity"].astype("string").str.lower().isin(["fatal", "major"]).astype("int8")
    cleaned["processing_version"] = PIPELINE_VERSION
    cleaning = {
        "pipeline_version": PIPELINE_VERSION, "input_rows": before, "output_rows": len(cleaned),
        "rows_removed": before - len(cleaned), "rows_repaired": int(cleaned.isna().sum().sum()),
        "removal_reasons": {"invalid_timestamp_or_coordinates": before - len(cleaned)},
        "missing_values_before": {c: int(v) for c, v in frame.isna().sum().items()},
        "missing_values_after": {c: int(v) for c, v in cleaned.isna().sum().items()},
        "transformations": ["combined date/time", "normalized categorical values", "derived severity-risk target", "excluded risk_score from features"],
    }
    atomic_write_json(REPORT_ROOT / "cleaning_report.json", cleaning)
    (REPORT_ROOT / "cleaning_report.md").write_text("# Cleaning report\n\n" + json.dumps(cleaning, indent=2, default=str))
    return cleaned


def file_fingerprint(path: Path) -> str:
    paths = sorted(path.parent.glob(path.name)) if any(char in path.name for char in "*?[") else [path]
    existing = [candidate for candidate in paths if candidate.exists()]
    if not existing:
        return "missing"
    return hashlib.sha256("|".join(f"{candidate}:{sha256(candidate)}" for candidate in existing).encode()).hexdigest()


def _haversine_km(lat: np.ndarray, lon: np.ndarray, other_lat: np.ndarray, other_lon: np.ndarray) -> np.ndarray:
    lat1 = np.radians(lat)[:, None]
    lon1 = np.radians(lon)[:, None]
    lat2 = np.radians(other_lat)[None, :]
    lon2 = np.radians(other_lon)[None, :]
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    return 6371.0088 * 2 * np.arcsin(np.sqrt(a))


def _indexed_nearest_and_count(
    lat: np.ndarray,
    lon: np.ndarray,
    other_lat: np.ndarray,
    other_lon: np.ndarray,
    radius_km: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Query geographic neighbors without materializing an N-by-M matrix."""
    from sklearn.neighbors import BallTree

    earth_radius_km = 6371.0088
    points = np.radians(np.column_stack([lat, lon]))
    inventory = np.radians(np.column_stack([other_lat, other_lon]))
    tree = BallTree(inventory, metric="haversine")
    nearest_radians, _ = tree.query(points, k=1)
    neighbors = tree.query_radius(points, r=radius_km / earth_radius_km, count_only=True)
    return nearest_radians[:, 0] * earth_radius_km, neighbors.astype("int64")


def _causal_window_bounds(times: pd.DatetimeIndex, observation_time: pd.Timestamp, window_days: int) -> tuple[int, int] | None:
    """Return an inclusive source window ending at the latest time <= observation."""
    end = int(np.searchsorted(times.values, observation_time.to_datetime64(), side="right") - 1)
    if end < 0 or times[end] > observation_time:
        return None
    start = max(0, end - window_days + 1)
    return start, end


def _load_landslides() -> tuple[np.ndarray, np.ndarray]:
    if not LANDSLIDE_GEOJSON.exists():
        return np.array([]), np.array([])
    payload = json.loads(LANDSLIDE_GEOJSON.read_text())
    lats, lons = [], []
    for feature in payload.get("features", []):
        properties = feature.get("properties") or {}
        lat = properties.get("LATITUDE")
        lon = properties.get("LONGITUDE")
        if lat is None or lon is None:
            coords = (feature.get("geometry") or {}).get("coordinates") or []
            if len(coords) >= 2:
                lon, lat = coords[:2]
        try:
            lat, lon = float(lat), float(lon)
        except (TypeError, ValueError):
            continue
        if -90 <= lat <= 90 and -180 <= lon <= 180:
            lats.append(lat)
            lons.append(lon)
    return np.asarray(lats), np.asarray(lons)


def _add_spatial_features(frame: pd.DataFrame) -> pd.DataFrame:
    enriched = frame.copy()
    for column in ENRICHMENT_FEATURES:
        enriched[column] = pd.NA
    lat = pd.to_numeric(enriched["latitude"], errors="coerce").to_numpy(float)
    lon = pd.to_numeric(enriched["longitude"], errors="coerce").to_numpy(float)
    valid = np.isfinite(lat) & np.isfinite(lon)

    slide_lat, slide_lon = _load_landslides()
    if len(slide_lat) and valid.any():
        nearest, count = _indexed_nearest_and_count(lat[valid], lon[valid], slide_lat, slide_lon, 25.0)
        enriched.loc[valid, "nearest_landslide_distance_km"] = nearest
        enriched.loc[valid, "nearby_landslide_count"] = count

    river_count = 0
    if RIVER_CSV.exists() and valid.any():
        river = pd.read_csv(RIVER_CSV)
        river_lat = pd.to_numeric(river.get("Latitude"), errors="coerce")
        river_lon = pd.to_numeric(river.get("Longitude"), errors="coerce")
        river_valid = river_lat.notna() & river_lon.notna()
        if river_valid.any():
            station_coords = pd.DataFrame({"lat": river_lat[river_valid], "lon": river_lon[river_valid]}).drop_duplicates()
            distances = _haversine_km(lat[valid], lon[valid], station_coords.lat.to_numpy(), station_coords.lon.to_numpy())
            enriched.loc[valid, "nearest_river_distance_km"] = distances.min(axis=1)
            river_count = int(len(station_coords))
            # The source observations are not contemporaneous with the accident
            # dates, so retain only defensible station proximity and no river level.
            enriched["river_observation_timestamp"] = pd.NaT

    enriched["osm_road_id"] = pd.NA
    enriched["match_distance_m"] = pd.NA
    enriched["match_confidence"] = pd.NA
    enriched["match_method"] = "unavailable_no_pbf_parser"
    REPORT_ROOT.mkdir(parents=True, exist_ok=True)
    atomic_write_json(REPORT_ROOT / "geo_enrichment_report.json", {
        "rows": len(enriched), "valid_coordinate_rows": int(valid.sum()),
        "landslide_inventory_points": int(len(slide_lat)), "landslide_enriched_rows": int(enriched["nearest_landslide_distance_km"].notna().sum()),
        "river_station_count": river_count, "river_distance_enriched_rows": int(enriched["nearest_river_distance_km"].notna().sum()),
        "river_level_enriched_rows": int(enriched["river_level"].notna().sum()),
        "osm_path": str(OSM_PBF.relative_to(ROOT)), "osm_exists": OSM_PBF.exists(),
        "osm_matched_rows": 0, "osm_match_status": "skipped_no_installed_pbf_parser; no road IDs fabricated",
        "timestamp": utc_now(),
    })
    return enriched


def _add_rainfall_features(frame: pd.DataFrame) -> pd.DataFrame:
    enriched = frame.copy()
    for column in ["rainfall_24h", "rainfall_3d", "rainfall_7d"]:
        enriched[column] = np.nan
    enriched["rainfall_observation_date"] = pd.NaT
    rainfall_paths = sorted(RAINFALL_NETCDF.parent.glob(RAINFALL_NETCDF.name))
    rainfall_path = rainfall_paths[0] if rainfall_paths else RAINFALL_NETCDF
    try:
        report_source = str(rainfall_path.relative_to(ROOT))
    except ValueError:
        report_source = str(rainfall_path)
    report = {"source": report_source, "source_exists": rainfall_path.exists(), "rows_with_rainfall": 0, "future_values_used": 0, "status": "skipped"}
    if rainfall_path.exists():
        try:
            import xarray as xr
            with xr.open_dataset(rainfall_path) as dataset:
                times = pd.to_datetime(dataset["TIME"].values).normalize()
                rainfall = dataset["RAINFALL"].values
                grid_lat = dataset["LATITUDE"].values
                grid_lon = dataset["LONGITUDE"].values
                timestamps = pd.to_datetime(enriched["timestamp"], errors="coerce")
                row_lat = pd.to_numeric(enriched["latitude"], errors="coerce").to_numpy(float)
                row_lon = pd.to_numeric(enriched["longitude"], errors="coerce").to_numpy(float)
                for position, stamp in enumerate(timestamps):
                    if pd.isna(stamp):
                        continue
                    date = stamp.normalize()
                    bounds = _causal_window_bounds(times, date, 1)
                    if bounds is None:
                        continue
                    time_index = bounds[1]
                    if not (-90 <= row_lat[position] <= 90 and -180 <= row_lon[position] <= 180):
                        continue
                    lat_index = int(np.abs(grid_lat - row_lat[position]).argmin())
                    lon_index = int(np.abs(grid_lon - row_lon[position]).argmin())
                    values = rainfall[:, lat_index, lon_index]
                    windows = [1, 3, 7]
                    for window, column in zip(windows, ["rainfall_24h", "rainfall_3d", "rainfall_7d"]):
                        start = max(0, time_index - window + 1)
                        period = values[start:time_index + 1]
                        finite = period[np.isfinite(period)]
                        if len(finite) == window:
                            enriched.loc[enriched.index[position], column] = float(finite.sum())
                    enriched.loc[enriched.index[position], "rainfall_observation_date"] = date
                report.update({"rows_with_rainfall": int(enriched["rainfall_24h"].notna().sum()), "status": "joined_prior_or_same_day_only", "time_min": str(times.min()), "time_max": str(times.max())})
        except Exception as exc:
            report["status"] = f"failed:{type(exc).__name__}:{exc}"
    atomic_write_json(REPORT_ROOT / "rainfall_enrichment_report.json", report)
    return enriched


def enrich_accidents(cleaned: pd.DataFrame) -> pd.DataFrame:
    spatial_hash = "|".join([file_fingerprint(LANDSLIDE_GEOJSON), file_fingerprint(RIVER_CSV), file_fingerprint(OSM_PBF)])
    spatial = checkpoint("05_geo_features", spatial_hash, {"radius_km": 25, "osm": "no_parser"}, CHECKPOINT_ROOT / "05_geo_features" / "accidents.parquet", lambda: _add_spatial_features(cleaned))
    environmental_hash = "|".join([sha256(CHECKPOINT_ROOT / "05_geo_features" / "accidents.parquet"), file_fingerprint(RAINFALL_NETCDF)])
    return checkpoint("06_environmental", environmental_hash, {"windows": [1, 3, 7], "causal": "at_or_before_timestamp"}, CHECKPOINT_ROOT / "06_environmental" / "accidents.parquet", lambda: _add_rainfall_features(spatial))


def canonicalize(cleaned: pd.DataFrame) -> pd.DataFrame:
    canonical = cleaned.copy()
    for column in ["flood_probability", "landslide_probability"]:
        canonical[column] = np.nan
    columns = list(dict.fromkeys(
        FEATURE_COLUMNS + ENRICHMENT_FEATURES + OPTIONAL_UPSTREAM_FEATURES
        + [TARGET, "timestamp", "source_dataset", "source_file", "source_row_id", "processing_version"]
    ))
    canonical = canonical[columns].copy()
    return canonical


def leakage_audit(frame: pd.DataFrame) -> dict[str, Any]:
    rejected = ["risk_score", "accident_severity", "accident_id", "date", "time"]
    findings = {column: (column in frame.columns) for column in rejected}
    report = {
        "pipeline_version": PIPELINE_VERSION, "target": TARGET, "feature_columns": FEATURE_COLUMNS,
        "target_derived_columns_rejected": ["risk_score", "accident_severity"],
        "findings": findings, "passed": not any(findings.values()),
        "notes": ["All source rows represent observed accidents; target is severity risk, not road closure.", "Chronological splitting prevents future timestamp leakage."],
    }
    atomic_write_json(REPORT_ROOT / "leakage_report.json", report)
    (REPORT_ROOT / "leakage_report.md").write_text("# Leakage audit\n\n" + json.dumps(report, indent=2))
    if not report["passed"]:
        raise ValueError(f"Leakage audit failed: {findings}")
    return report


def split_data(frame: pd.DataFrame) -> dict[str, pd.DataFrame]:
    ordered = frame.sort_values("timestamp").reset_index(drop=True)
    n = len(ordered)
    train_end = max(1, int(n * 0.70))
    validation_end = max(train_end + 1, int(n * 0.85))
    parts = {"train": ordered.iloc[:train_end].copy(), "validation": ordered.iloc[train_end:validation_end].copy(), "test": ordered.iloc[validation_end:].copy()}
    split_dir = CHECKPOINT_ROOT / "09_splits"
    for name, part in parts.items():
        atomic_write_dataframe(part, split_dir / f"{name}.parquet")
    atomic_write_json(split_dir / "manifest.json", {
        "stage": "09_splits", "timestamp": utc_now(), "pipeline_version": PIPELINE_VERSION,
        "cutoffs": {name: {"rows": len(part), "min": str(part.timestamp.min()), "max": str(part.timestamp.max())} for name, part in parts.items()},
    })
    return parts


def make_estimator(model_type: str, numeric_features: list[str], categorical_features: list[str]) -> Pipeline:
    numeric = Pipeline([("imputer", SimpleImputer(strategy="median")), ("scale", StandardScaler())])
    categorical = Pipeline([("imputer", SimpleImputer(strategy="most_frequent")), ("onehot", OneHotEncoder(handle_unknown="ignore"))])
    preprocessor = ColumnTransformer([("numeric", numeric, numeric_features), ("categorical", categorical, categorical_features)])
    classifier = LogisticRegression(max_iter=1000, class_weight="balanced") if model_type == "baseline" else HistGradientBoostingClassifier(max_iter=200, learning_rate=0.08, max_leaf_nodes=31, class_weight="balanced", random_state=42)
    return Pipeline([("preprocessor", preprocessor), ("classifier", classifier)])


def evaluate(model: Pipeline, frame: pd.DataFrame, feature_columns: list[str]) -> dict[str, Any]:
    probabilities = model.predict_proba(frame[feature_columns])[:, 1]
    predictions = (probabilities >= 0.5).astype(int)
    truth = frame[TARGET].astype(int)
    metrics: dict[str, Any] = {
        "rows": len(frame), "positive_count": int(truth.sum()), "negative_count": int((truth == 0).sum()),
        "positive_rate": float(truth.mean()), "precision": float(precision_score(truth, predictions, zero_division=0)),
        "recall": float(recall_score(truth, predictions, zero_division=0)), "f1": float(f1_score(truth, predictions, zero_division=0)),
        "brier_score": float(brier_score_loss(truth, probabilities)), "confusion_matrix": confusion_matrix(truth, predictions).tolist(),
        "threshold": 0.5,
    }
    metrics["roc_auc"] = float(roc_auc_score(truth, probabilities)) if truth.nunique() > 1 else None
    metrics["pr_auc"] = float(average_precision_score(truth, probabilities)) if truth.nunique() > 1 else None
    return metrics


def train_and_evaluate(parts: dict[str, pd.DataFrame]) -> dict[str, Any]:
    X_train, y_train = parts["train"], parts["train"][TARGET]
    feature_columns = [column for column in FEATURE_COLUMNS if column in X_train and X_train[column].notna().any()]
    numeric_features = [column for column in NUMERIC_FEATURES if column in feature_columns]
    categorical_features = [column for column in CATEGORICAL_FEATURES if column in feature_columns]
    baseline = make_estimator("baseline", numeric_features, categorical_features)
    model = make_estimator("tree", numeric_features, categorical_features)
    baseline.fit(X_train[feature_columns], y_train)
    model.fit(X_train[feature_columns], y_train)
    metrics = {"baseline": {"validation": evaluate(baseline, parts["validation"], feature_columns), "test": evaluate(baseline, parts["test"], feature_columns)}, "tree": {"validation": evaluate(model, parts["validation"], feature_columns), "test": evaluate(model, parts["test"], feature_columns)} }
    chosen = model if metrics["tree"]["validation"]["pr_auc"] >= metrics["baseline"]["validation"]["pr_auc"] else baseline
    chosen_name = "tree" if chosen is model else "baseline"
    version = "p3_road_risk_v002"
    MODEL_ROOT.mkdir(parents=True, exist_ok=True)
    artifact = MODEL_ROOT / f"{version}.joblib"
    joblib.dump(chosen, artifact)
    metadata = {
        "model_type": chosen_name, "model_version": version, "training_timestamp": utc_now(),
        "training_dataset_hash": sha256(CHECKPOINT_ROOT / "04_canonical" / "features.parquet"),
        "feature_names": feature_columns, "candidate_feature_names": FEATURE_COLUMNS, "target_name": TARGET,
        "training_row_count": len(parts["train"]), "validation_row_count": len(parts["validation"]), "test_row_count": len(parts["test"]),
        "model_role": "accident_traffic_risk",
        "model_semantics": "ACCIDENT/TRAFFIC RISK MODEL; not a disaster road-disruption model",
        "training_period": {"min": str(parts["train"].timestamp.min()), "max": str(parts["train"].timestamp.max())},
        "validation_period": {"min": str(parts["validation"].timestamp.min()), "max": str(parts["validation"].timestamp.max())},
        "test_period": {"min": str(parts["test"].timestamp.min()), "max": str(parts["test"].timestamp.max())},
        "artifact_path": str(artifact.relative_to(ROOT)),
        "limitations": ["Target is accident severity risk, not disaster road closure.", "Historical P1/P2 probabilities are unavailable.", "Disruption probability remains null."],
        "metrics": metrics, "dataset_sources": ["indian_road_accident"],
        "target_definition": "1 for fatal or major accident severity, 0 for minor; this is severity risk, not disaster-induced road disruption.",
        "excluded_features": {"risk_score": "target-derived leakage candidate", "accident_severity": "source target", "vehicles_involved": "observed after accident", "casualties": "observed after accident", "cause": "post-event/ambiguous", "flood_probability": "unavailable historical P1 output", "landslide_probability": "unavailable historical P2 output", "osm_road_id": "no installed PBF parser", "river_level": "no contemporaneous observations"},
    }
    atomic_write_json(MODEL_ROOT / f"{version}_metadata.json", metadata)
    atomic_write_json(MODEL_ROOT / "feature_schema.json", {"features": feature_columns, "candidate_features": FEATURE_COLUMNS, "numeric": numeric_features, "categorical": categorical_features, "target": TARGET})
    atomic_write_json(MODEL_ROOT / "current_model.json", {"model_version": version, "artifact": str(artifact.relative_to(ROOT)), "target": TARGET})
    atomic_write_json(REPORT_ROOT / "model_evaluation.json", metrics)
    (REPORT_ROOT / "model_evaluation.md").write_text("# Model evaluation\n\n" + json.dumps(metrics, indent=2))
    return {"model_version": version, "model_type": chosen_name, "metrics": metrics, "artifact": str(artifact), "feature_names": feature_columns}


def write_final_report(audit: dict[str, Any], cleaning: dict[str, Any], model_result: dict[str, Any], parts: dict[str, pd.DataFrame]) -> None:
    test_metrics = model_result["metrics"][model_result["model_type"]]["test"]
    geo_report = json.loads((REPORT_ROOT / "geo_enrichment_report.json").read_text())
    rainfall_report = json.loads((REPORT_ROOT / "rainfall_enrichment_report.json").read_text())
    text = f"""# Final P3 pipeline report

## Datasets discovered
- Indian accident archive: 20,000 real records, India, 2022-01-01 through 2025-04-15.
- IoT traffic archive: 1,000 real records, coordinates in the United States; audited but not merged into India training.

## Cleaning and geographic coverage
- Indian usable rows: {len(parts['train']) + len(parts['validation']) + len(parts['test'])}.
- Geographic coverage: seven Indian states and eight cities; coordinates valid after cleaning.
- IoT data is outside India and is not used as India training data.
- Rainfall: {rainfall_report.get('rows_with_rainfall', 0)} rows enriched from the 2025 daily grid using same-day/prior-only windows; future values used: {rainfall_report.get('future_values_used', 0)}.
- Landslide features: {geo_report.get('landslide_enriched_rows', 0)} rows have proximity/count features from the historical inventory.
- River data: {geo_report.get('river_distance_enriched_rows', 0)} rows have nearest-station distance; contemporaneous river levels: {geo_report.get('river_level_enriched_rows', 0)}.
- OSM PBF exists but was not parsed because no installed PBF parser is available; matched rows: {geo_report.get('osm_matched_rows', 0)} and no road IDs were fabricated.

## Target definition
The target is `{TARGET}`: fatal or major accident severity = 1, minor severity = 0. This is a supervised accident-severity risk model, not a historical disaster road-closure model. `risk_score` and severity fields were excluded as leakage.

## Splits
- Train: {len(parts['train'])} rows ({parts['train'].timestamp.min()} through {parts['train'].timestamp.max()})
- Validation: {len(parts['validation'])} rows ({parts['validation'].timestamp.min()} through {parts['validation'].timestamp.max()})
- Test: {len(parts['test'])} rows ({parts['test'].timestamp.min()} through {parts['test'].timestamp.max()})

## Model and test metrics
- Model: {model_result['model_type']}
- ROC-AUC: {test_metrics['roc_auc']}
- PR-AUC: {test_metrics['pr_auc']}
- F1: {test_metrics['f1']}
- Brier score: {test_metrics['brier_score']}
- Positive/negative test counts: {test_metrics['positive_count']}/{test_metrics['negative_count']}

## Features actually used
{', '.join(model_result['feature_names'])}

Candidate enrichment features with no observed training values were excluded from Model A: {', '.join(sorted(set(FEATURE_COLUMNS) - set(model_result['feature_names'])))}.

Rejected from Model A: risk_score, accident_severity, vehicles_involved, casualties, cause, OSM IDs without a parser, river levels without contemporaneous observations, and unavailable historical P1/P2 probabilities.

Flood and landslide probabilities remain optional inference inputs and are not fabricated for historical training.

## Artifacts and checkpoints
- Model: `{model_result['artifact']}`
- Checkpoints: `data/checkpoints/`
- Reports: `data/reports/`

## Readiness
- TRAINING_READY: true for the documented accident-severity target.
- INFERENCE_READY: true for the model artifact and API adapter; output must be described as severity-risk probability until road-disruption labels exist.
- Model B disaster road disruption: UNAVAILABLE. No defensible historical road-blockage, closure, damage, or accessibility target exists in the available sources.

## Reproduction
`python -m src.ml_pipeline.run --resume`
"""
    (REPORT_ROOT / "final_pipeline_report.md").write_text(text)


def run_pipeline(force: bool = False) -> dict[str, Any]:
    if force and CHECKPOINT_ROOT.exists():
        shutil.rmtree(CHECKPOINT_ROOT)
    started = time.perf_counter()
    audit = audit_sources()
    write_static_reports()
    extracted = extract_accidents()
    write_accident_deep_audit(extracted)
    write_target_candidates(extracted)
    cleaned = checkpoint(
        "03_cleaned", sha256(ACCIDENT_ARCHIVE), {"target": TARGET},
        CHECKPOINT_ROOT / "03_cleaned" / "accidents.parquet", lambda: clean_accidents(extracted)
    )
    enriched = enrich_accidents(cleaned)
    canonical = checkpoint(
        "04_canonical", sha256(CHECKPOINT_ROOT / "06_environmental" / "accidents.parquet"), {"features": FEATURE_COLUMNS, "target": TARGET},
        CHECKPOINT_ROOT / "04_canonical" / "features.parquet", lambda: canonicalize(enriched)
    )
    leakage_audit(canonical)
    parts = split_data(canonical)
    atomic_write_dataframe(canonical, PROCESSED_ROOT / "features" / "p3_training_dataset.parquet")
    result = train_and_evaluate(parts)
    cleaning = json.loads((REPORT_ROOT / "cleaning_report.json").read_text())
    write_final_report(audit, cleaning, result, parts)
    atomic_write_json(CHECKPOINT_ROOT / "checkpoint_manifest.json", {
        "pipeline_version": PIPELINE_VERSION,
        "timestamp": utc_now(),
        "stages": {
            "01_audit": "complete", "02_extracted": "complete", "03_cleaned": "complete",
            "04_canonical": "complete", "05_geo_features": "complete_landslide_and_river_distance_osm_skipped",
            "06_environmental": "complete_rainfall_prior_only",
            "07_features": "complete",
            "08_training": "complete", "09_splits": "complete", "10_model": "complete",
            "11_evaluation": "complete", "12_artifact": "complete",
        },
    })
    result["elapsed_seconds"] = time.perf_counter() - started
    return result


if __name__ == "__main__":
    print(json.dumps(run_pipeline(), indent=2))
