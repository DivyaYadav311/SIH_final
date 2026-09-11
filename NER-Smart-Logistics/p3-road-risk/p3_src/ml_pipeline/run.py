from __future__ import annotations

import argparse
import json

from .pipeline import run_pipeline


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the real-data P3 ML pipeline")
    parser.add_argument("--force", action="store_true", help="invalidate and rebuild checkpoints")
    parser.add_argument("--resume", action="store_true", help="reuse valid checkpoints (default)")
    args = parser.parse_args()
    print(json.dumps(run_pipeline(force=args.force), indent=2))


if __name__ == "__main__":
    main()
