# P3 API Contract

`POST /api/v1/road-risk/predict` accepts a road, timestamp, location, optional traffic/road/environment features, and optional P1/P2 probabilities.

The response contains:

- `risk_probability`: accident/traffic severity risk from the active P3 model
- `disruption_probability`: deterministic `hybrid_evidence_fusion_v2` evidence-fusion likelihood estimate; not a statistically calibrated supervised probability
- `operational_disruption_score`: the same hybrid score, retained for P4 compatibility
- `accessibility_score`: deterministic operational proxy, `100 * (1 - disruption_probability)`
- `evidence_completeness` and `disruption_confidence`: supporting-evidence availability, not statistical confidence
- `components`, `factors`, `evidence`, `disruption_category`, and deterministic explanation metadata
- `model_version`
- `road_disruption_model_status`: currently `insufficient_labels`

`GET /api/v1/road-risk/health` separates service health, risk-model availability, and road-disruption-model status. `GET /api/v1/road-risk/model` returns validated active-model metadata.

P1/P2 probabilities and environmental factors remain unavailable when not supplied; they are never fabricated or silently converted to zero.
