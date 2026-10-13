import numpy as np
import pandas as pd
import pytest

from apex_rca.canonical_scoring import score_canonical_incident


def make_metrics():
    rows = []
    for service, baseline, changed in [
        ("service-A", 10.0, 30.0),
        ("service-B", 20.0, 20.0),
    ]:
        for timestamp in range(0, 60):
            value = baseline if timestamp < 30 else changed
            rows.append({
                "timestamp": float(timestamp),
                "service": service,
                "metric": "unusual metric name",
                "value": value,
            })
    return pd.DataFrame(rows)


def test_scores_services_from_canonical_metrics():
    metrics = make_metrics()
    scores, details = score_canonical_incident(
        metrics,
        incident_time=30,
        reference_seconds=30,
        observed_seconds=30,
        min_samples=10,
    )
    assert scores["service-A"] > scores["service-B"]
    assert "unusual metric name" in dict(details["service-A"])


def test_incident_boundary_belongs_to_observed_window():
    metrics = make_metrics()
    scores, _ = score_canonical_incident(
        metrics,
        incident_time=30,
        reference_seconds=30,
        observed_seconds=30,
        min_samples=10,
    )
    assert set(scores) == {"service-A", "service-B"}


def test_missing_required_column_raises():
    with pytest.raises(ValueError, match="missing required columns"):
        score_canonical_incident(pd.DataFrame({"timestamp": [1]}), 1)


def test_non_finite_incident_time_raises():
    metrics = make_metrics()
    with pytest.raises(ValueError, match="finite"):
        score_canonical_incident(metrics, float("inf"))


def test_empty_window_raises():
    metrics = make_metrics()
    with pytest.raises(ValueError, match="No metric observations"):
        score_canonical_incident(
            metrics,
            incident_time=1000,
            reference_seconds=10,
            observed_seconds=10,
        )

def test_irregular_metric_timestamps_do_not_crash():
    rows = []
    for timestamp in range(0, 60, 2):
        rows.append({
            "timestamp": float(timestamp),
            "service": "service-A",
            "metric": "cpu",
            "value": 10.0 if timestamp < 30 else 30.0,
        })
    for timestamp in range(1, 60, 3):
        rows.append({
            "timestamp": float(timestamp),
            "service": "service-B",
            "metric": "latency",
            "value": 20.0 if timestamp < 30 else 40.0,
        })

    metrics = pd.DataFrame(rows)
    scores, details = score_canonical_incident(
        metrics,
        incident_time=30,
        reference_seconds=30,
        observed_seconds=30,
        min_samples=5,
    )

    assert set(scores) == {"service-A", "service-B"}
    assert scores["service-A"] > 0
    assert scores["service-B"] > 0
    assert "cpu" in dict(details["service-A"])
    assert "latency" in dict(details["service-B"])

def test_default_scoring_parameters_use_shared_config():
    from apex_rca.config import (
        ANOMALY_EFFECT_CAP,
        CANONICAL_OBSERVED_SECONDS,
        CANONICAL_REFERENCE_SECONDS,
        MIN_WINDOW_SAMPLES,
        TOP_K_METRICS,
    )

    import inspect

    parameters = inspect.signature(score_canonical_incident).parameters

    assert parameters["reference_seconds"].default == CANONICAL_REFERENCE_SECONDS
    assert parameters["observed_seconds"].default == CANONICAL_OBSERVED_SECONDS
    assert parameters["min_samples"].default == MIN_WINDOW_SAMPLES
    assert parameters["cap"].default == ANOMALY_EFFECT_CAP
    assert parameters["top_k_metrics"].default == TOP_K_METRICS

def test_duplicate_canonical_observations_raise_descriptive_error():
    metrics = pd.DataFrame({
        "timestamp": [0.0, 0.0],
        "service": ["service-A", "service-A"],
        "metric": ["cpu", "cpu"],
        "value": [59.0, 2.0],
    })

    with pytest.raises(
        ValueError,
        match="Duplicate canonical observations.*timestamp.*service.*metric",
    ):
        score_canonical_incident(
            metrics,
            incident_time=0,
            reference_seconds=30,
            observed_seconds=30,
            min_samples=1,
        )

