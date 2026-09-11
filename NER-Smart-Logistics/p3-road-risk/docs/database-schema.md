# P3 Data Schema

The accident-risk training data is stored in `data/processed/features/p3_training_dataset.parquet` with provenance fields, timestamp, location, canonical features, and `severity_risk_target`.

Historical road-closure evidence is stored in `data/processed/road_closure/road_closure_events.parquet` and `.csv`. It preserves `road_closed` values of 1, 0, or null, timestamp provenance, exact evidence text, source metadata, and nullable OSM matching fields.
