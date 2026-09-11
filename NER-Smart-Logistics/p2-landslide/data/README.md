# Training data

Provide a CSV containing verified observations. Every row needs the following
columns, plus a binary `landslide_occurred` label (`1` for a confirmed
landslide, `0` for a verified non-landslide observation):

```text
latitude,longitude,rainfall_1h_mm,rainfall_6h_mm,rainfall_24h_mm,rainfall_7d_mm,temperature_c,humidity_percent,elevation_m,slope_degree,aspect_degree,historical_landslide_count,landslide_occurred
```

`verified_landslide_observations.template.csv` contains this exact header for
starting a dataset. It intentionally has no observations: inventing rows or
using unverified absences as negatives would produce a misleading model.

For a runnable integration demo only, generate synthetic rows with
`python generate_demo_training_data.py`. The resulting
`demo_landslide_observations.csv` is deliberately labelled synthetic and is
not a replacement for verified observations.

The feature definitions and units must match the live pipeline exactly. Do
not create negative examples by randomly sampling unknown locations: a lack of
reported events is not evidence of no landslide. Hold out locations and time
periods not used in training before making real-world claims.

## GSI India susceptibility baseline

`build_gsi_susceptibility_dataset.py` creates an India-wide dataset from the
public GSI inventory. It uses mapped landslide locations as positives and
spatially separated pseudo-absence background points as negatives. Because the
inventory does not consistently provide event dates, this model estimates
**spatial susceptibility**, not a calibrated probability of a landslide today.

```bash
python build_gsi_susceptibility_dataset.py
python train_model.py --data data/gsi_india_susceptibility.csv --model-version landslide_india_inventory_susceptibility_v1 --training-data-kind gsi_inventory_with_pseudo_absences
```

Train with:

```bash
python train_model.py --data data/verified_landslide_observations.csv
```

This writes `models/landslide_model_v1.pkl`, which the API loads automatically.
Confirm that the API is using it with:

```text
GET /api/v1/model-status
```

The endpoint reports the saved holdout metrics and creation time. Those metrics
are useful checks, not proof that the model will generalize to a new region;
keep a location- and time-separated evaluation set for that decision.
