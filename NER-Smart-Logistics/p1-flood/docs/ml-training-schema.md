# P1 ML Training Contract

The training command consumes a daily, spatially indexed CSV. One row represents
one prediction location on one prediction date. The target must describe an
event that occurs after the feature timestamp; do not use post-event rainfall,
flooded area, or impact fields as predictors.

## Required columns

```text
date,segment_id,flood_event
```

`flood_event` is binary: `1` means the chosen flood definition occurred within
the forecast horizon after `date`; `0` means the location was observed without
that event. Missing labels are rejected. Flood-event rows alone are not enough
to train a classifier; non-event rows must be generated from documented source
coverage.

## Optional feature columns

```text
rainfall_1d_mm
rainfall_3d_mm
rainfall_7d_mm
rainfall_14d_mm
rainfall_30d_mm
rainfall_anomaly_7d
rainfall_anomaly_30d
elevation_m
river_proximity_km
latitude
longitude
month
```

Missing feature values are permitted and are kept as missing by the tree model.
The current model uses a chronological 60%/20%/20% train/validation/test split.
Calibration is fit on validation data and metrics are reported only on the
future test period.

## Training

```bash
cd p1-flood
venv/bin/python src/train_model.py --table data/processed/training_samples.csv
```

This writes `models/p1_flood_model.joblib` and a sidecar metrics JSON. The live
scorer uses the artifact automatically; if it is absent, P1 explicitly reports
`heuristic_fallback` in `contributing_factors.scoring_method`.
