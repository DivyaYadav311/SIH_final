# P3 Architecture

P3 currently exposes an accident/traffic risk model trained from real Indian accident records. It is not a disaster road-disruption model.

The inference path loads the active model from `models/current_model.json`, validates its metadata and feature schema, and returns `risk_probability`. It then passes that unchanged accident/traffic output, optional P1/P2 predictions, and available causal evidence to the deterministic hybrid engine in `src/hybrid.py`. The engine returns the evidence-fusion likelihood estimate and keeps `operational_disruption_score` equal to it.

Optional P1/P2 probabilities are represented through provider interfaces in `src/providers/upstream.py`. Unavailable providers return null rather than fabricated values.

The hybrid engine is the replacement point for a future supervised Model B. Until explicit closure and open/reopened labels support training and calibration, no supervised disruption model is trained.
