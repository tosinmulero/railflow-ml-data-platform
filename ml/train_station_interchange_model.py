from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

import mlflow.sklearn
import numpy as np
import pandas as pd
import yaml
from mlflow.models import infer_signature
from sklearn.compose import TransformedTargetRegressor
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import (
    HistGradientBoostingRegressor,
    RandomForestRegressor,
)
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
    median_absolute_error,
    r2_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

import mlflow
from mlflow import MlflowClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = PROJECT_ROOT / "config" / "ml_training.yaml"


def load_config(
    config_path: Path | None = None,
) -> dict[str, Any]:
    path = config_path or DEFAULT_CONFIG

    with path.open(
        "r",
        encoding="utf-8",
    ) as handle:
        return yaml.safe_load(handle)


def project_path(relative_path: str) -> Path:
    return PROJECT_ROOT / relative_path


def dataset_fingerprint(
    paths: list[Path],
) -> str:
    digest = hashlib.sha256()

    for path in sorted(paths):
        digest.update(path.name.encode("utf-8"))

        with path.open("rb") as handle:
            while True:
                chunk = handle.read(1024 * 1024)

                if not chunk:
                    break

                digest.update(chunk)

    return digest.hexdigest()


def load_training_data(
    config: dict[str, Any],
) -> tuple[pd.DataFrame, str]:
    data_config = config["data"]

    parquet_dir = project_path(data_config["parquet_dir"])

    parquet_files = sorted(parquet_dir.glob("*.parquet"))

    if not parquet_files:
        raise FileNotFoundError(f"No Parquet files found in {parquet_dir}")

    id_column = data_config["id_column"]
    target_column = data_config["target"]["column"]
    feature_columns = list(data_config["features"])

    required_columns = [
        id_column,
        *feature_columns,
        target_column,
    ]

    frames: list[pd.DataFrame] = []

    for parquet_file in parquet_files:
        frame = pd.read_parquet(
            parquet_file,
            columns=required_columns,
        )

        frames.append(frame)

    dataset = pd.concat(
        frames,
        ignore_index=True,
    )

    dataset = dataset.drop_duplicates(
        subset=[id_column],
        keep="last",
    )

    numeric_columns = [
        *feature_columns,
        target_column,
    ]

    for column in numeric_columns:
        dataset[column] = pd.to_numeric(
            dataset[column],
            errors="coerce",
        )

    dataset = dataset.replace(
        [np.inf, -np.inf],
        np.nan,
    )

    dataset = dataset.dropna(subset=[target_column])

    dataset = dataset[dataset[target_column] >= 0].copy()

    if len(dataset) < 500:
        raise RuntimeError(f"Training dataset is unexpectedly small: {len(dataset)} rows")

    if dataset[id_column].duplicated().any():
        raise RuntimeError("Duplicate entity keys remain after deduplication.")

    fingerprint = dataset_fingerprint(parquet_files)

    return dataset, fingerprint


def build_model(
    model_name: str,
    config: dict[str, Any],
) -> TransformedTargetRegressor:
    model_config = config["models"][model_name]
    random_state = config["split"]["random_state"]

    model_type = model_config["type"]

    if model_type == "dummy_median":
        estimator = DummyRegressor(
            strategy="median",
        )

    elif model_type == "random_forest":
        estimator = RandomForestRegressor(
            n_estimators=model_config["n_estimators"],
            max_depth=model_config["max_depth"],
            min_samples_leaf=model_config["min_samples_leaf"],
            max_features=model_config["max_features"],
            n_jobs=model_config["n_jobs"],
            random_state=random_state,
        )

    elif model_type == "hist_gradient_boosting":
        estimator = HistGradientBoostingRegressor(
            learning_rate=model_config["learning_rate"],
            max_iter=model_config["max_iter"],
            max_leaf_nodes=model_config["max_leaf_nodes"],
            l2_regularization=model_config["l2_regularization"],
            random_state=random_state,
        )

    else:
        raise ValueError(f"Unsupported model type: {model_type}")

    pipeline = Pipeline(
        steps=[
            (
                "imputer",
                SimpleImputer(strategy="median"),
            ),
            (
                "regressor",
                estimator,
            ),
        ]
    )

    return TransformedTargetRegressor(
        regressor=pipeline,
        func=np.log1p,
        inverse_func=np.expm1,
        check_inverse=False,
    )


def regression_metrics(
    y_true: pd.Series | np.ndarray,
    y_pred: np.ndarray,
) -> dict[str, float]:
    actual = np.asarray(
        y_true,
        dtype=float,
    )

    predicted = np.asarray(
        y_pred,
        dtype=float,
    )

    predicted = np.clip(
        predicted,
        a_min=0.0,
        a_max=None,
    )

    absolute_error = np.abs(actual - predicted)

    rmsle = float(np.sqrt(np.mean((np.log1p(actual) - np.log1p(predicted)) ** 2)))

    return {
        "mae": float(
            mean_absolute_error(
                actual,
                predicted,
            )
        ),
        "rmse": float(
            math.sqrt(
                mean_squared_error(
                    actual,
                    predicted,
                )
            )
        ),
        "median_absolute_error": float(
            median_absolute_error(
                actual,
                predicted,
            )
        ),
        "r2": float(
            r2_score(
                actual,
                predicted,
            )
        ),
        "rmsle": rmsle,
        "p90_absolute_error": float(
            np.quantile(
                absolute_error,
                0.90,
            )
        ),
    }


def configure_mlflow(
    config: dict[str, Any],
) -> str:
    mlflow_config = config["mlflow"]

    tracking_db = project_path(mlflow_config["tracking_db"])

    artifact_root = project_path(mlflow_config["artifact_root"])

    tracking_db.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    artifact_root.mkdir(
        parents=True,
        exist_ok=True,
    )

    tracking_uri = "sqlite:///" + tracking_db.resolve().as_posix()

    mlflow.set_tracking_uri(tracking_uri)

    mlflow.set_registry_uri(tracking_uri)

    experiment_name = mlflow_config["experiment_name"]

    experiment = mlflow.get_experiment_by_name(experiment_name)

    if experiment is None:
        mlflow.create_experiment(
            experiment_name,
            artifact_location=(artifact_root.resolve().as_uri()),
        )

    mlflow.set_experiment(experiment_name)

    return tracking_uri


def log_model_run(
    model_name: str,
    model: TransformedTargetRegressor,
    model_config: dict[str, Any],
    x_train: pd.DataFrame,
    y_train: pd.Series,
    x_test: pd.DataFrame,
    y_test: pd.Series,
    dataset_sha256: str,
    release: str,
    feature_columns: list[str],
    target_column: str,
) -> dict[str, Any]:
    with mlflow.start_run(run_name=model_name) as run:
        model.fit(
            x_train,
            y_train,
        )

        predictions = model.predict(x_test)

        predictions = np.clip(
            predictions,
            0.0,
            None,
        )

        metrics = regression_metrics(
            y_test,
            predictions,
        )

        mlflow.set_tags(
            {
                "project": "railflow",
                "pipeline_stage": "stage_8_ml",
                "release": release,
                "model_name": model_name,
                "problem_type": "regression",
                "target_semantic": ("annual_station_interchanges"),
            }
        )

        mlflow.log_params(
            {
                "model_name": model_name,
                "model_type": model_config["type"],
                "target_column": target_column,
                "target_transform": "log1p",
                "feature_count": len(feature_columns),
                "train_rows": len(x_train),
                "test_rows": len(x_test),
                "dataset_sha256": (dataset_sha256),
                **{f"model__{key}": value for key, value in model_config.items() if key != "type"},
            }
        )

        mlflow.log_metrics(metrics)

        mlflow.log_dict(
            {
                "features": feature_columns,
                "target": target_column,
                "target_transform": "log1p",
                "dataset_sha256": (dataset_sha256),
                "release": release,
            },
            "feature_contract.json",
        )

        signature = infer_signature(
            x_train,
            model.predict(x_train),
        )

        model_info = mlflow.sklearn.log_model(
            sk_model=model,
            name="model",
            signature=signature,
            input_example=x_train.head(5),
            serialization_format="cloudpickle",
        )

        return {
            "model_name": model_name,
            "run_id": run.info.run_id,
            "model_uri": (model_info.model_uri),
            **metrics,
        }


def create_model_card(
    config: dict[str, Any],
    dataset_rows: int,
    train_rows: int,
    test_rows: int,
    dataset_sha256: str,
    comparison: pd.DataFrame,
    champion: dict[str, Any],
    improvement_pct: float,
) -> None:
    output_path = project_path(config["outputs"]["model_card"])

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    feature_names = "\n".join(f"- `{feature}`" for feature in config["data"]["features"])

    metrics_table = comparison[
        [
            "model_name",
            "mae",
            "rmse",
            "rmsle",
            "r2",
        ]
    ].to_markdown(index=False)

    content = f"""# RailFlow Station Interchange Model

## Objective

Estimate annual station interchange volume for Great Britain railway
stations using ORR passenger-flow characteristics.

This is a cross-sectional demand-estimation model, not a future-year
forecasting model.

## Dataset

- Release: `{config["project"]["release"]}`
- Total usable rows: `{dataset_rows}`
- Training rows: `{train_rows}`
- Holdout rows: `{test_rows}`
- Dataset SHA-256: `{dataset_sha256}`

## Target

- Column: `{config["data"]["target"]["column"]}`
- Semantic meaning: annual station interchanges
- Training transform: `log1p`
- Prediction output: original interchange-count scale

## Features

{feature_names}

## Explicit Leakage Controls

The model excludes:

- the target itself (`c6`);
- every target-derived `feature__c6...` field;
- `c5`, which is a station ranking derived from passenger usage;
- `c13`, which is the National Location Code identifier;
- `station_key`, which is an entity identifier.

## Candidate Results

{metrics_table}

## Champion

- Algorithm: `{champion["model_name"]}`
- Registered model: `{config["mlflow"]["registered_model_name"]}`
- Registry alias: `{config["mlflow"]["champion_alias"]}`
- RMSLE: `{champion["rmsle"]:.6f}`
- MAE: `{champion["mae"]:.2f}`
- RMSE: `{champion["rmse"]:.2f}`
- R²: `{champion["r2"]:.6f}`
- RMSLE improvement over median baseline: `{improvement_pct:.2f}%`

## Validation Design

A deterministic 80/20 station-level holdout is used because the current
project contains one annual ORR release.

## Known Limitations

1. There is only one annual observation per station, so this experiment
   does not establish temporal forecasting performance.
2. The dataset is highly skewed: a small number of major interchange
   stations carry substantially larger volumes.
3. Network topology, service frequency, disruption history, timetable
   density and geographic catchment variables are not yet included.
4. This model should therefore be treated as an ML engineering and
   station-demand estimation baseline, not as a production passenger
   forecast.

## Next Production Improvements

- Add multiple historical ORR releases.
- Add timetable and service-frequency features.
- Add station geography and network-topology features.
- Use temporal validation.
- Add drift and performance monitoring.
- Serve the champion through an inference API.
"""

    output_path.write_text(
        content,
        encoding="utf-8",
    )


def main() -> None:
    config = load_config()

    dataset, fingerprint = load_training_data(config)

    id_column = config["data"]["id_column"]

    feature_columns = list(config["data"]["features"])

    target_column = config["data"]["target"]["column"]

    if target_column in feature_columns:
        raise RuntimeError("Target leakage detected: target is present in feature list.")

    leakage_columns = set(config["data"]["excluded_leakage_columns"])

    if leakage_columns.intersection(feature_columns):
        raise RuntimeError("Target-derived features detected in training features.")

    x = dataset[feature_columns].copy()

    y = dataset[target_column].copy()

    x_train, x_test, y_train, y_test = train_test_split(
        x,
        y,
        test_size=config["split"]["test_size"],
        random_state=config["split"]["random_state"],
    )

    tracking_uri = configure_mlflow(config)

    print("=" * 72)
    print("RAILFLOW - STAGE 8 MACHINE LEARNING")
    print("=" * 72)
    print(f"Rows             : {len(dataset)}")
    print(f"Unique stations  : {dataset[id_column].nunique()}")
    print(f"Training rows    : {len(x_train)}")
    print(f"Test rows        : {len(x_test)}")
    print(f"Target           : {target_column} / annual interchanges")
    print(f"Features         : {feature_columns}")
    print(f"Dataset SHA-256  : {fingerprint}")
    print(f"MLflow tracking  : {tracking_uri}")
    print()

    model_names = [
        "baseline",
        "random_forest",
        "hist_gradient_boosting",
    ]

    results: list[dict[str, Any]] = []

    for model_name in model_names:
        print(f"Training: {model_name}")

        model = build_model(
            model_name,
            config,
        )

        result = log_model_run(
            model_name=model_name,
            model=model,
            model_config=config["models"][model_name],
            x_train=x_train,
            y_train=y_train,
            x_test=x_test,
            y_test=y_test,
            dataset_sha256=fingerprint,
            release=config["project"]["release"],
            feature_columns=feature_columns,
            target_column=target_column,
        )

        results.append(result)

        print(f"  RMSLE={result['rmsle']:.6f} MAE={result['mae']:.2f} R2={result['r2']:.6f}")

    comparison = pd.DataFrame(results).sort_values(
        by=config["selection"]["metric"],
        ascending=True,
    )

    comparison_path = project_path(config["outputs"]["comparison_csv"])

    comparison_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    comparison.to_csv(
        comparison_path,
        index=False,
    )

    baseline = next(item for item in results if item["model_name"] == "baseline")

    candidates = [item for item in results if item["model_name"] != "baseline"]

    selection_metric = config["selection"]["metric"]

    champion = min(
        candidates,
        key=lambda item: item[selection_metric],
    )

    baseline_metric = baseline[selection_metric]

    champion_metric = champion[selection_metric]

    if baseline_metric > 0:
        improvement_pct = (baseline_metric - champion_metric) / baseline_metric * 100.0
    else:
        improvement_pct = 0.0

    if champion_metric >= baseline_metric:
        raise RuntimeError(f"No candidate model beat the median baseline on {selection_metric}.")

    registered_name = config["mlflow"]["registered_model_name"]

    model_version = mlflow.register_model(
        model_uri=champion["model_uri"],
        name=registered_name,
    )

    client = MlflowClient()

    alias = config["mlflow"]["champion_alias"]

    client.set_registered_model_alias(
        name=registered_name,
        alias=alias,
        version=model_version.version,
    )

    client.set_model_version_tag(
        name=registered_name,
        version=model_version.version,
        key="validation_status",
        value="approved",
    )

    client.set_model_version_tag(
        name=registered_name,
        version=model_version.version,
        key="selection_metric",
        value=selection_metric,
    )

    client.set_model_version_tag(
        name=registered_name,
        version=model_version.version,
        key="dataset_sha256",
        value=fingerprint,
    )

    champion_output = {
        **champion,
        "registered_model_name": (registered_name),
        "registered_model_version": (str(model_version.version)),
        "alias": alias,
        "selection_metric": (selection_metric),
        "baseline_rmsle": baseline["rmsle"],
        "improvement_pct": (improvement_pct),
        "dataset_sha256": (fingerprint),
        "training_rows": len(x_train),
        "test_rows": len(x_test),
    }

    champion_path = project_path(config["outputs"]["champion_json"])

    champion_path.write_text(
        json.dumps(
            champion_output,
            indent=2,
        ),
        encoding="utf-8",
    )

    create_model_card(
        config=config,
        dataset_rows=len(dataset),
        train_rows=len(x_train),
        test_rows=len(x_test),
        dataset_sha256=fingerprint,
        comparison=comparison,
        champion=champion,
        improvement_pct=improvement_pct,
    )

    print()
    print("=" * 72)
    print("MODEL COMPARISON")
    print("=" * 72)

    print(
        comparison[
            [
                "model_name",
                "mae",
                "rmse",
                "rmsle",
                "r2",
            ]
        ].to_string(index=False)
    )

    print()
    print("=" * 72)
    print("CHAMPION MODEL")
    print("=" * 72)
    print(f"Model       : {champion['model_name']}")
    print(f"RMSLE       : {champion['rmsle']:.6f}")
    print(f"MAE         : {champion['mae']:.2f}")
    print(f"R2          : {champion['r2']:.6f}")
    print(f"Improvement : {improvement_pct:.2f}% vs baseline")
    print(f"Registry    : {registered_name}")
    print(f"Version     : {model_version.version}")
    print(f"Alias       : {alias}")
    print()
    print("STAGE 8A ML TRAINING: PASS")


if __name__ == "__main__":
    main()
