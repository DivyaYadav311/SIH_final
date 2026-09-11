# NER Smart Logistics (SIH26002)

AI-based Smart Logistics and Accessibility Intelligence Platform for the North Eastern
Region — combines flood, landslide, and road-disruption risk into route optimization
and supply-chain decisions, surfaced through a control-tower dashboard.

## Team / module ownership

| Module | Owner | Folder |
|---|---|---|
| Flood Intelligence | P1 | `p1-flood/` |
| Landslide Intelligence | P2 | `p2-landslide/` |
| Road Risk & Accessibility | P3 | `p3-road-risk/` |
| Route Optimization | P4 | `p4-routing/` |
| Logistics & Supply Chain | P5 | `p5-logistics/` |
| Response & Control Tower | P6 | `p6-control-tower/` |

## Before you write model code

Read **`docs/api-contracts.md`** — it defines the exact JSON output every module must
produce so downstream modules can consume it without knowing how it was built. If you
need to change your module's output shape, tell whoever consumes it first.

Each module folder has its own `data/sample_output.json` (placeholder, schema-correct)
so you can start building against it immediately — you don't have to wait for the
upstream module to be "done."

## Rules
1. Work independently inside your own folder.
2. Don't modify another person's folder without telling them.
3. Source code in `src/`, models in `models/`, datasets/snapshots in `data/`, tests in
   `tests/`.
4. Common schemas/contracts live in `shared/` and `docs/` — everyone can propose changes,
   but ping affected owners before merging.
5. Don't commit large model files or full datasets (see `.gitignore`) — commit a small
   `sample_output.json` instead, and document how to regenerate/download the rest.
6. Push regularly so the repo stays current for integration.

## Getting started (per module)
```bash
cd p1-flood          # or whichever module is yours
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
# see that folder's README.md for how to run it
```
