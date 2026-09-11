# P3 Data

Place supplied training archives under `data/raw/training/`:

- `indian_road_accident/indian_road_accident.zip`
- `iot_traffic_dataset/iot.zip`

The pipeline discovers the CSV member inside each archive and records archive size and SHA256 in `data/manifests/source_manifest.csv`. Download URLs are intentionally recorded as `unknown` when the project does not know them; they must not be invented.

Run the real pipeline from this project directory:

```bash
python -m src.ml_pipeline.run
```

Use `--force` to invalidate generated checkpoints. Normal execution reuses valid checkpoints under `data/checkpoints/` when input hashes and configuration match.

Generated reports are under `data/reports/`, the canonical training dataset is `data/processed/features/p3_training_dataset.parquet`, and model artifacts are under `models/`.

Raw archives, NetCDF files, GeoJSON, OSM PBF, Parquet checkpoints, and model binaries are local inputs or generated outputs and should not be committed. Verify the dataset license and original source before redistribution.
