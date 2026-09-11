# API Contracts — NER Smart Logistics

This document defines the **exact output format** each module must produce so that
downstream modules can consume it without needing to know how it was built.

Rule of thumb: **the output schema is a promise**. If you need to change it, ping the
person(s) who consume it before you do.

---

## Shared conventions (apply to every module)

- **Geo key**: all modules key their outputs by `segment_id` (a road/district identifier
  shared across the project — defined in `shared/constants/segments.json`, TBD by whoever
  owns the road network data, likely P3/P4). Until that file exists, use `district_name`
  as a placeholder key.
- **Date format**: ISO 8601, `YYYY-MM-DD` (add `T HH:MM` only if you're doing sub-daily
  forecasts).
- **Probabilities**: floats in `[0, 1]`, not percentages.
- **File format**: JSON. Every module's `src/` should have a function that returns a
  Python dict/list matching its schema below, plus a way to dump it to
  `data/sample_output.json` for other teams to test against.
- **Timezone**: IST for all timestamps unless stated otherwise.

---

## P1 — Flood Intelligence (owner: You)

**Input:** IMD / Open-Meteo rainfall data + terrain (Bhuvan) + historical flood data (CWC/WRIS)

**Output schema:**

```json
{
  "segment_id": "NER-D-045",
  "date": "2026-09-05",
  "flood_probability": 0.72,
  "confidence": 0.6,
  "contributing_factors": {
    "rainfall_7day_mm": 210.4,
    "elevation_m": 42.0,
    "river_proximity_km": 1.2,
    "historical_flood_frequency": null
  },
  "source_timestamp": "2026-09-05T06:00:00+05:30"
}
```

- `flood_probability` is the only **required** field downstream modules rely on.
- `confidence` and `contributing_factors` are optional/nice-to-have — include them if
  you can, since P6 (Control Tower) can use them for explainability, but P3 should not
  hard-depend on them.

**Consumed by:** P3 (Road Risk & Accessibility)

---

## P2 — Landslide Intelligence

**Input:** rainfall + terrain + satellite (Sentinel) + historical landslides (ISRO Landslide Atlas)

**Output schema:**

```json
{
  "segment_id": "NER-D-045",
  "date": "2026-09-05",
  "landslide_probability": 0.41,
  "confidence": 0.55,
  "source_timestamp": "2026-09-05T06:00:00+05:30"
}
```

**Consumed by:** P3 (Road Risk & Accessibility)

---

## P3 — Road Risk & Accessibility

**Input:** P1 output + P2 output + road characteristics + incident reports

**Output schema:**

```json
{
  "segment_id": "NER-D-045",
  "date": "2026-09-05",
  "disruption_probability": 0.58,
  "accessibility_score": 0.44,
  "status": "at_risk",
  "source_timestamp": "2026-09-05T06:00:00+05:30"
}
```

- `status` suggested enum: `"open" | "at_risk" | "closed"` — P4 can use this directly for
  routing instead of re-deriving thresholds from the raw probability.

**Consumed by:** P4 (Route Optimization)

---

## P4 — Route Optimization

**Input:** road network + P3 output

**Output schema:**

```json
{
  "request_id": "req-001",
  "origin": "NER-D-010",
  "destination": "NER-D-090",
  "routes": [
    {
      "type": "fastest",
      "path": ["NER-D-010", "NER-D-045", "NER-D-090"],
      "eta_minutes": 132,
      "risk_score": 0.3
    },
    {
      "type": "safest",
      "path": ["NER-D-010", "NER-D-022", "NER-D-090"],
      "eta_minutes": 168,
      "risk_score": 0.05
    }
  ]
}
```

**Consumed by:** P5 (Logistics & Supply Chain)

---

## P5 — Logistics & Supply Chain

**Input:** shipments + inventory + demand + P4 routes + risk

**Output schema:**

```json
{
  "shipment_id": "SHIP-2026-0912",
  "priority": "high",
  "shortage_prediction": {
    "location": "NER-D-090",
    "item": "medical_supplies",
    "shortage_in_days": 3
  },
  "recommended_warehouse": "NER-WH-04",
  "recommended_route_id": "req-001"
}
```

**Consumed by:** P6 (Control Tower)

---

## P6 — Response & Control Tower

**Input:** all of the above + live incident feed

**Output:** alerts, rerouting recommendations, what-if simulation results, dashboard data.
Since P6 aggregates everything, its schema will likely be finalized last — P6 owner should
draft it once P1–P5 schemas are stable, and this doc updated accordingly.

---

## Open items to settle as a team (do this before writing model logic)

1. Finalize `segment_id` — what's the actual unit (district, road segment, grid cell)?
   Whoever owns the road-network data (P3/P4) should publish `shared/constants/segments.json`
   ASAP since P1 and P2 both key off it.
2. Forecast horizon — is everyone predicting "today's risk" or "risk over next N days"?
   Needs to be consistent across P1–P3.
3. Update frequency — hourly? daily? Affects how P6's dashboard refreshes.
