import numpy as np

from ml.train_station_interchange_model import (
    build_model,
    load_config,
    regression_metrics,
)


def test_perfect_regression_metrics():
    actual = np.array([0.0, 10.0, 100.0])

    metrics = regression_metrics(
        actual,
        actual,
    )

    assert metrics["mae"] == 0.0
    assert metrics["rmse"] == 0.0
    assert metrics["rmsle"] == 0.0
    assert metrics["r2"] == 1.0


def test_target_is_not_a_feature():
    config = load_config()

    target = config["data"]["target"]["column"]

    features = config["data"]["features"]

    assert target not in features


def test_target_derived_features_are_excluded():
    config = load_config()

    features = set(config["data"]["features"])

    leakage = set(config["data"]["excluded_leakage_columns"])

    assert not features.intersection(leakage)


def test_identifier_fields_are_not_features():
    config = load_config()

    features = set(config["data"]["features"])

    identifiers = set(config["data"]["excluded_identifier_columns"])

    assert not features.intersection(identifiers)


def test_all_three_models_build():
    config = load_config()

    for model_name in (
        "baseline",
        "random_forest",
        "hist_gradient_boosting",
    ):
        model = build_model(
            model_name,
            config,
        )

        assert model is not None
