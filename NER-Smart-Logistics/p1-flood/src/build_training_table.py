"""Build a catchment-level P1 training table from INDOFLOODS and IPED.

The historical inventory is an event catalogue, so non-event rows are treated
as weak negatives: no inventory event is recorded for the forecast window.
This assumption is recorded in the output metadata and should be discussed in
model evaluation.
"""

from __future__ import annotations

import argparse
import tempfile
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

from spatial_features import add_river_proximity


def _extract_year(archive: zipfile.ZipFile, year: int, target: Path) -> Path:
    member = f"03_IPED_RES_0P10/IPED_Mean/IPED_mean_{year}.nc"
    with archive.open(member) as source, target.open("wb") as destination:
        while chunk := source.read(1024 * 1024):
            destination.write(chunk)
    return target


def _load_rainfall(archive_path: Path, gauges: pd.DataFrame, start_year: int, end_year: int) -> pd.DataFrame:
    rows = []
    gauge_ids = gauges["gauge_id"].to_numpy()
    latitudes = xr.DataArray(gauges["latitude"].to_numpy(), dims="gauge")
    longitudes = xr.DataArray(gauges["longitude"].to_numpy(), dims="gauge")
    with zipfile.ZipFile(archive_path) as archive, tempfile.TemporaryDirectory(prefix="p1_iped_") as temp:
        for year in range(start_year, end_year + 1):
            path = _extract_year(archive, year, Path(temp) / f"{year}.nc")
            with xr.open_dataset(path, engine="h5netcdf") as dataset:
                values = dataset["pcp"].sel(lat=latitudes, lon=longitudes, method="nearest").transpose("gauge", "time").to_numpy()
                dates = pd.to_datetime(dataset["time"].to_numpy()).tz_localize(None)
            count = len(dates)
            rows.append(pd.DataFrame({
                "gauge_id": np.repeat(gauge_ids, count),
                "date": np.tile(dates, len(gauge_ids)),
                "rainfall_mm": values.reshape(-1),
            }))
            print(f"  processed IPED {year}")
    return pd.concat(rows, ignore_index=True)


def _rolling_features(rainfall: pd.DataFrame) -> pd.DataFrame:
    rainfall = rainfall.sort_values(["gauge_id", "date"]).reset_index(drop=True)
    grouped = rainfall.groupby("gauge_id", sort=False)["rainfall_mm"]
    for window in (1, 3, 7, 14, 30):
        rainfall[f"rainfall_{window}d_mm"] = grouped.transform(
            lambda values, window=window: values.rolling(window, min_periods=window).sum()
        )
    rainfall["month"] = rainfall["date"].dt.month
    return rainfall


def _weak_labels(events: pd.DataFrame, dates: pd.DataFrame) -> pd.DataFrame:
    event_dates = pd.to_datetime(events["date"], errors="coerce").dropna()
    positive_rows = []
    for gauge_id, group in events.assign(date=event_dates).groupby("gauge_id"):
        for event_date in group["date"]:
            for offset in range(4):
                positive_rows.append({"gauge_id": gauge_id, "date": event_date - pd.Timedelta(days=offset)})
    positives = pd.DataFrame(positive_rows).drop_duplicates()
    labeled = dates.merge(positives.assign(flood_event=1), on=["gauge_id", "date"], how="left")
    labeled["flood_event"] = labeled["flood_event"].fillna(0).astype(int)
    labeled["label_type"] = np.where(labeled["flood_event"].eq(1), "observed_event_window", "weak_negative_no_inventory_event")
    return labeled


def build_table(raw_dir: Path, iped_zip: Path, output: Path, start_year: int = 1991, end_year: int = 2020, negative_ratio: int = 5) -> pd.DataFrame:
    event_path = raw_dir.parent.parent / "processed" / "indofloods_event_candidates.csv"
    if not event_path.exists():
        raise FileNotFoundError("Run prepare_indofloods.py before build_training_table.py")
    events = pd.read_csv(event_path)
    events["date"] = pd.to_datetime(events["date"], errors="coerce")
    events = events[events["date"].dt.year.between(start_year, end_year)]
    gauges = events[["gauge_id", "latitude", "longitude"]].drop_duplicates()
    rainfall = _load_rainfall(iped_zip, gauges, start_year, end_year)
    rainfall = _rolling_features(rainfall)
    table = _weak_labels(events[["gauge_id", "date"]], rainfall)
    table = table.dropna(subset=["rainfall_30d_mm"]).copy()
    table = table.merge(gauges, on="gauge_id", how="left", validate="many_to_one")
    table["segment_id"] = table["gauge_id"]
    river_zip = raw_dir.parent / "rivers" / "river_network_shape.zip"
    if river_zip.exists():
        table = add_river_proximity(table, river_zip)
    else:
        table["river_proximity_km"] = np.nan
        table["river_feature_source"] = "unavailable"
    table["rainfall_anomaly_7d"] = np.nan
    table["rainfall_anomaly_30d"] = np.nan

    positives = table[table["flood_event"].eq(1)]
    negatives = table[table["flood_event"].eq(0)]
    rng = np.random.default_rng(42)
    sampled_groups = []
    positive_counts = positives.groupby("gauge_id").size()
    for gauge_id, group in negatives.groupby("gauge_id"):
        target = max(50, int(positive_counts.get(gauge_id, 0)) * negative_ratio)
        sampled_groups.append(group.sample(n=min(target, len(group)), random_state=int(rng.integers(0, 2**31 - 1))))
    sampled_negatives = pd.concat(sampled_groups, ignore_index=True) if sampled_groups else negatives.iloc[0:0]
    result = pd.concat([positives, sampled_negatives], ignore_index=True).sort_values(["date", "gauge_id"])
    result.to_csv(output, index=False)
    print(f"Wrote {len(result)} rows to {output}")
    print(f"  positive rows: {int(result.flood_event.sum())}")
    print(f"  weak negative rows: {int((result.flood_event == 0).sum())}")
    print(f"  catchments: {result.gauge_id.nunique()}")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    default_raw = Path(__file__).resolve().parent.parent / "data/raw/hydrosense"
    parser.add_argument("--raw-dir", type=Path, default=default_raw)
    parser.add_argument("--iped-zip", type=Path, default=default_raw / "03_IPED_RES_0P10.zip")
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parent.parent / "data/processed/training_samples.csv")
    args = parser.parse_args()
    build_table(args.raw_dir, args.iped_zip, args.output)


if __name__ == "__main__":
    main()
