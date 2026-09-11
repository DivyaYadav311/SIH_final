# P1 — Flood Intelligence

Predicts `flood_probability` per segment/district for the NER Smart Logistics platform.
See `docs/api-contracts.md` (project root) for the full output schema — that's the
contract this module must satisfy for P3 (Road Risk) to consume it.

## Inputs
- **Rainfall** — [Open-Meteo](https://open-meteo.com/) (free, no key required) — current + forecast
- **Elevation** — [Open-Meteo Elevation API](https://open-meteo.com/en/docs/elevation-api) (free, no key required)
- **River proximity** — [OpenStreetMap Overpass API](https://wiki.openstreetmap.org/wiki/Overpass_API) (free, no key required) — finds the nearest mapped waterway
- **Historical flood data** — [CWC / India-WRIS](https://www.cwc.gov.in/en/water-resources-information-system-wris) — not yet wired in (no simple live API; needs a downloaded dataset, see TODO below)
- **Bhuvan** (ISRO) — optional upgrade path for official terrain/landslide data, but requires registering for a free access token at bhuvan-app1.nrsc.gov.in — not required for the current pipeline

## Setup
```bash
cd p1-flood
python -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Run
```bash
python src/fetch_rainfall.py       # pulls real rainfall data into data/rainfall_raw.json
python src/fetch_terrain.py        # pulls real elevation + river-distance into data/terrain_raw.json
python src/flood_score.py          # combines both into flood_probability, writes data/sample_output.json
```
Run `fetch_rainfall.py` and `fetch_terrain.py` before `flood_score.py` — the scoring
script reads their output files. If `terrain_raw.json` is missing, `flood_score.py`
still runs, just without the terrain adjustment (falls back to a neutral 0.5 factor).

## ML training

P1 supports a calibrated gradient-boosted flood model in addition to the original
heuristic. The model is deliberately opt-in: `flood_score.py` uses the trained
artifact when it exists and otherwise keeps the transparent heuristic fallback.
This makes deployment safe while historical labels are being assembled.

The training table contract is documented in `docs/ml-training-schema.md`. It must
contain a future-looking binary `flood_event` label; flood-event rows alone are not
enough to train a classifier.

```bash
cd p1-flood
venv/bin/python src/train_model.py \
  --table data/processed/training_samples.csv
```

To normalize the supplied INDOFLOODS events and geometry first:

```bash
venv/bin/python src/prepare_indofloods.py
```

This creates an observed-event candidate table and catchment coordinates. It is
intentionally not treated as a complete training set because it contains flood
events but no verified non-flood examples.

To build the first reproducible training table from IPED:

```bash
venv/bin/python src/build_training_table.py
```

This uses the nearest 0.1-degree IPED grid cell for each catchment, writes
30-day rainfall features, and adds approximate nearest-river distance from the
NWIC River Network when `data/raw/rivers/river_network_shape.zip` is present.
Non-event rows are explicitly marked as weak negatives because an event inventory
cannot prove that an unlisted day was flood-free. CartoDEM is not required; the
elevation feature remains missing in historical training until an elevation raster
is available, while live inference can continue using Open-Meteo elevation.

Training uses chronological 60%/20%/20% train/validation/test periods. Probability
calibration is fit only on the validation period, and final metrics are reported on
the future test period. The model artifact is written to `models/` and is ignored by
git along with raw datasets.

The current live response includes `contributing_factors.scoring_method`, which is
either `ml_calibrated` or `heuristic_fallback`.

The current artifact version is stored in the model metadata. The spatial source
audit can be regenerated with:

```bash
venv/bin/python src/spatial_features.py
```

## Folder structure
```
p1-flood/
├── src/
│   ├── fetch_rainfall.py    # real rainfall data (Open-Meteo)
│   ├── fetch_terrain.py     # real elevation + river distance (Open-Meteo + OSM Overpass)
│   └── flood_score.py       # combines rainfall + terrain -> flood_probability
├── models/                  # trained models go here (gitignored — don't commit weights)
├── data/                    # cached API responses / sample output (gitignored except sample_output.json)
├── tests/                   # unit tests
└── requirements.txt
```

## Status / TODO
- [x] Rainfall — real, live (Open-Meteo)
- [x] Terrain (elevation + river proximity) — real, live (Open-Meteo + OSM Overpass)
- [x] Scoring logic combining rainfall + terrain (rule-based, weighted formula)
- [ ] Historical flood frequency — the INDOFLOODS/IPED model is trained, but a
      separate defensible frequency lookup by segment_id is still needed
- [ ] Optionally swap in Bhuvan's official terrain/landslide data if someone registers
      for an access token
- [ ] Decide: keep the hand-built formula, or train an ML model once we have labeled
      historical flood incidents to validate against
- [ ] Confirm `segment_id` scheme with P3/P4 (see open items in `docs/api-contracts.md`)
- [x] Build a reproducible INDOFLOODS/IPED training table with documented weak negatives
- [x] Add auditable NWIC river proximity to training when the river archive is present
- [ ] Validate Northeast-region coverage and final segment-to-catchment mapping
- [ ] Replace weak negatives with verified flood-free or inundation-based labels

## Notes
Every input feeding the score is real data. `historical_flood_frequency` remains
`null`, and historical non-event labels remain explicitly weak. The active artifact
is a calibrated gradient-boosted baseline using rainfall, coordinates, month, and
NWIC river proximity; elevation is available at live inference time but is not part
of historical training without CartoDEM-compatible coverage.
