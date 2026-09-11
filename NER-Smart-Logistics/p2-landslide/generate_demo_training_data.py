"""Create deterministic demo data for exercising the ML pipeline.

The rows are synthetic and must not be used to make real-world safety claims.
Replace them with verified labelled observations before deployment.
"""

import argparse
import csv
import math
import random
from pathlib import Path

from app.scoring import FEATURE_ORDER


def create_demo_dataset(output_path: str | Path, rows: int = 600) -> Path:
    """Generate repeatable, physically plausible feature combinations and labels."""
    if rows < 50:
        raise ValueError("At least 50 demo rows are required.")

    rng = random.Random(20260906)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as destination:
        writer = csv.DictWriter(destination, fieldnames=FEATURE_ORDER + ["landslide_occurred"])
        writer.writeheader()
        for _ in range(rows):
            rain_1h = round(rng.gammavariate(1.3, 7.0), 2)
            rain_6h = round(rain_1h + rng.gammavariate(1.8, 13.0), 2)
            rain_24h = round(rain_6h + rng.gammavariate(2.2, 22.0), 2)
            rain_7d = round(rain_24h + rng.gammavariate(3.0, 55.0), 2)
            slope = round(rng.triangular(0, 58, 27), 2)
            historical_count = min(8, int(rng.expovariate(0.8)))
            humidity = round(rng.uniform(38, 99), 2)
            row = {
                "latitude": round(rng.uniform(8, 36), 5),
                "longitude": round(rng.uniform(68, 97), 5),
                "rainfall_1h_mm": rain_1h,
                "rainfall_6h_mm": rain_6h,
                "rainfall_24h_mm": rain_24h,
                "rainfall_7d_mm": rain_7d,
                "temperature_c": round(rng.uniform(-2, 34), 2),
                "humidity_percent": humidity,
                "elevation_m": round(rng.uniform(20, 4200), 2),
                "slope_degree": slope,
                "aspect_degree": round(rng.uniform(0, 360), 2),
                "historical_landslide_count": historical_count,
            }
            # A deliberately simple generative rule produces a learnable demo
            # signal; it is not an empirical landslide susceptibility formula.
            log_odds = (
                -6.0
                + 0.023 * rain_24h
                + 0.006 * rain_7d
                + 0.085 * slope
                + 0.19 * historical_count
                + 0.018 * max(humidity - 60, 0)
            )
            probability = 1 / (1 + math.exp(-log_odds))
            row["landslide_occurred"] = int(rng.random() < probability)
            writer.writerow(row)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Create synthetic demo training data.")
    parser.add_argument("--output", default="data/demo_landslide_observations.csv")
    parser.add_argument("--rows", type=int, default=600)
    arguments = parser.parse_args()
    output = create_demo_dataset(arguments.output, arguments.rows)
    print(f"Created synthetic demo dataset at {output}")


if __name__ == "__main__":
    main()
