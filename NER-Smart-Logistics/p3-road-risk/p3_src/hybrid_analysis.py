from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from p3_src.hybrid import load_hybrid_config

ROOT = Path(__file__).resolve().parents[1]
REPORT_ROOT = ROOT / "data" / "reports"
CLOSURE_DATA = ROOT / "data" / "processed" / "road_closure" / "road_closure_events.parquet"


def main() -> None:
    config = load_hybrid_config()
    events = pd.read_parquet(CLOSURE_DATA)
    target_counts = {
        "closed": int((events.road_closed == 1).sum()),
        "open": int((events.road_closed == 0).sum()),
        "unknown": int(events.road_closed.isna().sum()),
        "dated_closed": int(((events.road_closed == 1) & events.event_timestamp.notna()).sum()),
        "dated_open": int(((events.road_closed == 0) & events.event_timestamp.notna()).sum()),
    }
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dataset": str(CLOSURE_DATA.relative_to(ROOT)),
        "target_definition": "explicit road closure/blockage = 1; explicit open/reopened/restored = 0; unknown retained as null",
        "target_counts": target_counts,
        "component_audit": {
            "flood_probability": {"source": "P1 provider", "historical_coverage": "unavailable", "inference_available": True, "leakage_risk": "provider timestamp must be <= prediction timestamp"},
            "landslide_probability": {"source": "P2 provider", "historical_coverage": "unavailable", "inference_available": True, "leakage_risk": "provider timestamp must be <= prediction timestamp"},
            "risk_probability": {"source": "P3 v002", "definition": "accident/traffic severity risk", "historical_coverage": "20,000 Indian accident records", "leakage_risk": "target is not road closure; do not relabel"},
            "incident_risk": {"source": "none", "historical_coverage": "unavailable", "inference_available": "optional external input", "leakage_risk": "must be supplied from prediction-time evidence"},
        },
        "normalization": {"all_components": "inputs must already be bounded in [0,1]; no batch normalization"},
        "candidate_methods": {
            "univariate_association": "not meaningful: no dated negative class",
            "multivariate_logistic_regression": "not fit: zero explicit open labels",
            "constrained_weight_optimization": "not fit: no temporally aligned binary target",
            "chronological_validation": "not possible for binary closure target",
            "geographic_robustness": "not possible for learned weights",
        },
        "baselines": {
            "equal_available_components": "selected as transparent engineering prior",
            "flood_landslide_only": "not evaluated against a valid target",
            "risk_only": "operational fallback when only risk is available; not a closure baseline",
        },
        "selected_weights": config["weights"],
        "weight_source": config["weight_source"],
        "weight_method": config["method"],
        "weight_stability": "not estimable without temporally aligned labels",
        "geographic_analysis": "not estimable for learned weights; source spans 20 states but has no open class",
        "rationale": "Equal prior weights are the least-assumptive transparent fallback across the three valid bounded signals. Incident risk receives zero because no independently supported incident-risk component exists. These weights are not learned, calibrated, or empirically proven.",
        "operational_score": "sum(effective_weight_i * component_i), renormalized over available positive-prior components",
        "disruption_probability_available": False,
    }
    (REPORT_ROOT / "hybrid_weight_analysis.json").write_text(json.dumps(report, indent=2))
    (REPORT_ROOT / "hybrid_weight_analysis.md").write_text("# Hybrid weight analysis\n\n" + json.dumps(report, indent=2))
    final = REPORT_ROOT / "phase7_final_report.md"
    final.write_text(f"""# Phase 7 final report

## Decision
Empirical weight learning was not possible. The closure evidence has {target_counts['closed']} positives, {target_counts['open']} explicit opens, {target_counts['dated_closed']} dated positives, and {target_counts['dated_open']} dated opens. The selected weights are an engineering prior, not learned or calibrated.

## Selected configuration
- Method: `{config['method']}`
- Source: `{config['weight_source']}`
- Weights: `{json.dumps(config['weights'], sort_keys=True)}`
- Missing components: renormalize across available positive-prior components.

## Formula
`operational_disruption_score = sum(effective_weight_i * normalized_component_i)`

Inputs are already bounded in [0,1]. `accessibility_score = 100 * (1 - operational_disruption_score)`. Neither output is a calibrated disaster-closure probability.

## API/P4 bridge
P4 should consume `operational_disruption_score`, which is the same deterministic `hybrid_evidence_fusion_v2` score as `disruption_probability`. `risk_probability` remains accident/traffic risk. The hybrid value is an evidence-fusion likelihood estimate, not a supervised calibrated probability.

## Limitations
- No explicit dated open/reopened source records.
- P1/P2 historical replay unavailable.
- Incident-risk component unavailable.
- Weight stability and geographic robustness cannot be estimated without a valid target.

See `data/reports/hybrid_weight_analysis.json` for the complete audit.
""")


if __name__ == "__main__":
    main()
