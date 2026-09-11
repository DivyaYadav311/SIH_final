# P3 Integration Guide

P4 should consume `operational_disruption_score` (equal to `disruption_probability`) for routing. `risk_probability` remains the existing accident/traffic model output. The disruption value is an evidence-fusion likelihood estimate, not a calibrated supervised probability. `evidence_completeness` and `disruption_confidence` describe evidence availability, not statistical confidence. Accessibility is bounded from 0 to 100 using `100 * (1 - disruption_probability)`.

P1 and P2 can provide probabilities through the provider interfaces. If either provider is unavailable or times out, its probability remains null. P3 does not import P1/P2 internals or duplicate their models.

GenAI is optional explanation-only functionality. It receives the deterministic result, cannot change its score or weights, and prediction uses the deterministic fallback if no client is configured or a client fails.
