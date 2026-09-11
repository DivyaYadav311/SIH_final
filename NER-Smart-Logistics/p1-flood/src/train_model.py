"""CLI for training P1 from a canonical daily training CSV.

The CSV must contain date, segment_id, flood_event, and any subset of the
feature columns listed in ml_model.py. Missing feature values are allowed and
remain missing through the model; missing labels are rejected.
"""

import argparse
from pathlib import Path

import pandas as pd

from ml_model import DEFAULT_ARTIFACT, train_model


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--table", type=Path, required=True)
    parser.add_argument("--artifact", type=Path, default=DEFAULT_ARTIFACT)
    parser.add_argument("--model-version", default="p1_flood_v2_river_enriched")
    args = parser.parse_args()
    metrics = train_model(pd.read_csv(args.table), args.artifact, model_version=args.model_version)
    print("P1 model trained")
    for key, value in metrics.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    main()
