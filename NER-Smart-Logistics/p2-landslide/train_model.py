"""Command-line entry point for training the landslide classifier."""

import argparse

from app.training import train_model, write_metrics


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the landslide risk classifier.")
    parser.add_argument("--data", required=True, help="CSV containing labelled observations")
    parser.add_argument("--output", default="models/landslide_model_v1.pkl", help="Path for the joblib model artifact")
    parser.add_argument("--model-version", default="landslide_logistic_regression_v1")
    parser.add_argument("--training-data-kind", default="verified_observations")
    arguments = parser.parse_args()
    metrics = train_model(
        arguments.data,
        arguments.output,
        model_version=arguments.model_version,
        training_data_kind=arguments.training_data_kind,
    )
    print(f"Saved trained model to {arguments.output}")
    print(write_metrics(metrics))


if __name__ == "__main__":
    main()
