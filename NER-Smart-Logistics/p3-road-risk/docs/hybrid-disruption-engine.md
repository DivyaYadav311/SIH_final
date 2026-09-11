# P3 Hybrid Disruption Engine

`compute_hybrid_disruption` is the single authoritative P3 calculation path.
The current `disruption_probability` is an **evidence-fusion road disruption
likelihood estimate, not a supervised calibrated probability**. It remains
deterministic, explainable, bounded, and reproducible. `operational_disruption_score`
is exactly the same final score for P4 compatibility.

## Inputs and missing data

The engine accepts the canonical nested contract: P1 flood probability, P2
landslide probability, existing P3 `risk_probability`, environmental and
terrain factors, road vulnerability, and nearby incident factors. Every
numeric factor is validated in `[0, 1]`; invalid values, non-finite numbers,
and malformed objects are rejected. `null` means unknown and is never changed
to zero.

## Formula

For each component, only available evidence receives its configured weight and
the available weights are renormalized:

```text
flood_environment = weighted_average(
  rainfall, river, flood_vulnerability, nearby_flood
)
flood_disruption = flood_probability * flood_environment

landslide_environment = weighted_average(
  rainfall, slope, terrain, nearby_landslide
)
landslide_disruption = landslide_probability * landslide_environment

traffic_disruption = weighted_average(
  risk_probability, nearby_accident, congestion
)

raw_disruption = weighted_average(
  flood_disruption, landslide_disruption, traffic_disruption
)
synergy_bonus = 0.10 * clamp((min(flood_probability, landslide_probability)-0.50)*2, 0, 1)
pre_modifier = raw_disruption + synergy_bonus
vulnerability_modifier = 0.90 + 0.20 * road_vulnerability
disruption_probability = clamp(pre_modifier * vulnerability_modifier, 0, 1)
```

The top-level weights are flood `0.40`, landslide `0.40`, and traffic `0.20`.
The exact v2 configuration is in `models/hybrid_weight_config.json`. Hazard
probabilities are primary signals; environmental, incident, spatial, and
temporal values modify their exposure instead of being treated as independent
closure labels. Nearby flood evidence is explicitly included with a small
configurable weight to avoid silently discarding it while limiting correlated
double-counting.

## Spatial and temporal evidence

`compute_proximity_factor(distance_km, scale_km)` returns
`exp(-distance_km / scale_km)`. Incident metadata can provide
`distance_km` and `event_timestamp`; each available modifier is applied to its
base incident factor. Temporal decay is `exp(-age_hours / tau_hours)` with a
24-hour default. A future event raises a validation error and cannot influence
the prediction. When metadata is absent, a supplied incident factor is used
unchanged; no coordinates or timestamps are invented.

## Road vulnerability and evidence completeness

The modifier uses an explicit `road_vulnerability_factor` when supplied, or
the available `road_type_vulnerability_factor` as a conservative current
proxy. It is bounded to `0.90..1.10` and is omitted when no vulnerability
evidence exists. Richer OSM-derived attributes can later populate the same
factor without changing the scoring contract.

`evidence_completeness` is the fraction of the twelve expected core factors
that are available. `disruption_confidence` is `LOW` below `0.50`, `MEDIUM`
from `0.50` through below `0.80`, and `HIGH` at or above `0.80`. Confidence
represents evidence completeness, not statistical model calibration.

Categories are `LOW` (`<0.25`), `MODERATE` (`0.25` to `<0.50`), `HIGH`
(`0.50` to `<0.75`), and `CRITICAL` (`>=0.75`).

## Leakage and model boundaries

Only evidence available at or before the prediction timestamp is accepted.
Post-event imagery, future closure/reopening records, future weather, and
future labels are not prediction inputs. The existing accident/traffic model
is preserved and supplies `risk_probability`; it is not retrained and its
leaky historical fields are not used by the hybrid engine.

LLM/GenAI is intentionally not part of the numerical calculation. The
deterministic explanation metadata and `generate_explanation` function use
only calculated evidence, drivers, and missing fields.

## API and future Model B

The API preserves `risk_probability`, `operational_disruption_score`, and
existing response fields while adding v2 components, factors, evidence,
contributions, decay context, and explanation metadata. `score_contributions`
are generated from the same top-level calculation and sum to the unclamped
final score, including synergy and vulnerability modification.

`disruption_method` is `hybrid_evidence_fusion_v2`, leaving a clean replacement
point for a future `physical_road_disruption_model` after defensible closure
and open/reopened labels, temporal validation, leakage review, and calibration
are available. No Model B is trained here.

## Deterministic Explanation

The deterministic engine returns explanation metadata directly from its
calculated components, factors, evidence, and missing fields. This explanation
is part of the authoritative P3 result; no LLM, external provider, web search,
or secret configuration is involved. It identifies the primary and secondary
drivers and acknowledges unavailable evidence without treating missing data as
safe.