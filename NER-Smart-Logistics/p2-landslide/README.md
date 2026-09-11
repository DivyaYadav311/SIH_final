# Live Landslide Prediction Agent

This version no longer asks the caller to manually send rainfall, humidity,
elevation, slope, aspect, land cover, or historical landslide count.
It accepts **latitude + longitude** and fetches the features live.

## Live data pipeline

1. **Open-Meteo Forecast API** → current temperature/humidity + hourly precipitation.
2. **Open-Meteo Elevation API / Copernicus GLO-90** → elevation for a 3×3 terrain neighbourhood.
3. **Terrain calculation** → slope and aspect are calculated from the live DEM using the Horn method.
4. **NASA COOLR** → count of historical landslide events within 25 km.
5. **OpenStreetMap Overpass** → best-effort nearby land-use/natural feature mapped to a land-cover class.
6. **Risk engine** → current heuristic, or a trained joblib classifier if supplied.
7. **Sentinel-2 satellite metadata** → optional recent-scene discovery. If it
   is unavailable, the weather/terrain prediction pipeline continues normally.

> The default risk engine is still a transparent heuristic. It is **not** a
> scientifically validated landslide probability model. For a production/SIH
> claim, train and validate a classifier on historical landslide and
> non-landslide samples before calling the output a calibrated probability.

## Run locally

```bash
python -m venv .venv
# Windows:
.venv\\Scripts\\activate
# macOS/Linux:
# source .venv/bin/activate

pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Open Swagger at `http://localhost:8000/docs`.

## API reference

### `GET /health`

Returns service liveness without calling external providers.

```json
{"status": "ok", "mode": "live-api"}
```

### `GET /api/v1/live-features`

Query parameters are `latitude` (-90 to 90) and `longitude` (-180 to 180).
This endpoint fetches the environmental inputs and returns the values used by
the risk engine.

Example request:

```text
GET /api/v1/live-features?latitude=27.584&longitude=91.873
```

The response includes `features`, provider names in `data_sources`, and a
`source_status` map. `live` means the value came from that provider for this
request. `calculated_from_live_elevation` identifies slope/aspect derived by
the Horn method. `fallback` identifies a neutral demo value used because a
provider was unavailable; it is never presented as live data.

```json
{
  "latitude": 27.584,
  "longitude": 91.873,
  "features": {
    "rainfall_1h_mm": 0.1,
    "rainfall_6h_mm": 0.6,
    "rainfall_24h_mm": 1.3,
    "rainfall_7d_mm": 49.2,
    "temperature_c": 14.9,
    "humidity_percent": 90.0,
    "elevation_m": 2788.0,
    "slope_degree": 10.88,
    "aspect_degree": 226.44,
    "land_cover": "grassland",
    "historical_landslide_count": 0
  },
  "source_status": {
    "weather": "live",
    "elevation": "live",
    "terrain_derivatives": "calculated_from_live_elevation",
    "historical_landslides": "fallback",
    "land_cover": "live"
  },
  "timestamp": "2026-09-06T11:30:55Z"
}
```

### `POST /api/v1/predictions/landslide`

The request body requires only coordinates. `location_id` is optional.

```json
{
  "location_id": "LOC_001",
  "latitude": 27.584,
  "longitude": 91.873
}
```

The response contains the exact `live_features` sent to the scoring layer,
the resulting `landslide_probability`, `risk_level`, `confidence`,
`model_version`, provider names, and `source_status`.

```json
{
  "location_id": "LOC_001",
  "latitude": 27.584,
  "longitude": 91.873,
  "landslide_probability": 0.1842,
  "risk_level": "LOW",
  "confidence": 0.896,
  "model_version": "landslide_heuristic_v0",
  "timestamp": "2026-09-06T11:30:55Z",
  "live_features": {"rainfall_1h_mm": 0.1, "slope_degree": 10.88},
  "data_sources": {"weather": "Open-Meteo Forecast API"},
  "source_status": {"weather": "live"}
}
```

The abbreviated nested objects above are illustrative; the actual response
contains every field shown in the live-features response. Invalid coordinates
return `422`. An unexpected pipeline failure returns `502`, while provider
failures are represented by `source_status: "fallback"` and do not stop
prediction.

## Prediction request

Only coordinates are required:

```json
{
  "location_id": "LOC_001",
  "latitude": 27.5840,
  "longitude": 91.8730
}
```

Example with curl:

```bash
curl -X POST http://localhost:8000/api/v1/predictions/landslide ^
  -H "Content-Type: application/json" ^
  -d @sample_request.json
```

For PowerShell, use `curl.exe` instead of `curl` if needed.

## Inspect live features without predicting

```text
GET /api/v1/live-features?latitude=27.584&longitude=91.873
```

This is useful while integrating the frontend because you can verify the
actual values being fetched from each API.

## Response

The prediction response includes:

- `landslide_probability`
- `risk_level`
- `confidence`
- `live_features` — the exact feature values used for the prediction
- `data_sources` — which services supplied those features
- UTC `timestamp`
- `satellite_observation` — recent Sentinel-2 scene metadata when available;
  otherwise an explicit unavailable/no-scene status with the textual/live
  feature prediction still returned.

## Trained model support

### India inventory-trained susceptibility model

The included GSI trainer creates an India-wide **susceptibility** baseline from
real mapped landslides and spatially separated pseudo-absence points:

```bash
python build_gsi_susceptibility_dataset.py
python train_model.py --data data/gsi_india_susceptibility.csv --model-version landslide_india_inventory_susceptibility_v1 --training-data-kind gsi_inventory_with_pseudo_absences
```

It is not a same-day event forecast: the inventory does not consistently
contain event dates, so it cannot associate occurrences with historic rainfall.
The reported validation metrics use a geographic grid holdout to reduce
nearby-point leakage; they still do not replace an independent field survey.

For an immediately runnable **demo** model, generate the included synthetic
training data and train it:

```bash
python generate_demo_training_data.py
python train_model.py --data data/demo_landslide_observations.csv
```

This creates `models/landslide_model_v1.pkl`, which is loaded automatically.
The demo data proves the ML integration works but is not real-world validation.
Use the verified-observation workflow below before deployment.

Train a model from a CSV of verified, labelled observations with:

```bash
python train_model.py --data data/verified_landslide_observations.csv
```

The trainer validates the feature columns, requires both classes, makes a
stratified holdout split, and reports ROC-AUC and average precision. It saves
a compatible sklearn logistic-regression model with the exact `FEATURE_ORDER`
in `app/scoring.py` as:

```text
models/landslide_model_v1.pkl
```

and set:

```text
MODEL_PATH=models/landslide_model_v1.pkl
MODEL_VERSION=landslide_logistic_regression_v1
```

The API contract does not need to change.

After training, verify the active model at:

```text
GET /api/v1/model-status
```

It returns `"mode": "trained"` only when a compatible artifact is actually
loaded. Otherwise the service explicitly reports `"mode": "heuristic"`.

No model artifact is currently included in `models/`, so the service currently
uses `landslide_heuristic_v0`. The joblib branch is used only when a
compatible artifact exists at `MODEL_PATH`; its presence alone does not prove
that the model was trained or validated. Do not describe the heuristic output
as a calibrated probability.

## API notes

Open-Meteo documents its forecast endpoint as providing hourly weather data
for coordinates, and its elevation API uses a 90 m Copernicus DEM. NASA's
COOLR service is intended to expose landslide event points through an ArcGIS
FeatureServer. The default legacy COOLR URL currently returns 404 in the live
environment tested for this service; set `NASA_COOLR_URL` to a currently valid
deployment to enable live historical counts. Until then,
`historical_landslides` is explicitly marked `fallback` and contributes zero.
OpenStreetMap is used only as a contextual land-use source; it is not a
complete global land-cover dataset.

For public demos, show the source names in your UI and keep attribution for
the underlying data providers.
