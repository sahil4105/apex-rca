import pandas as pd

from apex_rca.canonical import CanonicalIncident, DatasetCapabilities


def valid_metrics():
    return pd.DataFrame({
        "timestamp": [1000, 1060],
        "service": ["checkout", "checkout"],
        "metric": ["cpu", "cpu"],
        "value": [20.0, 85.0],
    })


def test_valid_canonical_incident_passes_validation():
    incident = CanonicalIncident(
        incident_id="test-001",
        dataset="synthetic",
        metrics=valid_metrics(),
        incident_time=1060,
        capabilities=DatasetCapabilities(
            metrics=True,
            incident_timestamps=True,
        ),
    )

    assert incident.validate() == []


def test_missing_canonical_metric_columns_are_reported():
    incident = CanonicalIncident(
        incident_id="test-002",
        dataset="synthetic",
        metrics=pd.DataFrame({"time": [1000], "cpu": [20.0]}),
    )

    errors = incident.validate()

    assert len(errors) == 1
    assert "timestamp" in errors[0]
    assert "service" in errors[0]
    assert "metric" in errors[0]
    assert "value" in errors[0]


def test_missing_service_identifier_is_rejected():
    metrics = valid_metrics()
    metrics.loc[0, "service"] = None

    incident = CanonicalIncident(
        incident_id="test-003",
        dataset="synthetic",
        metrics=metrics,
    )

    assert any("service contains missing values" in error
               for error in incident.validate())


def test_missing_modalities_can_be_represented():
    incident = CanonicalIncident(
        incident_id="test-004",
        dataset="metrics-only",
        metrics=valid_metrics(),
        capabilities=DatasetCapabilities(metrics=True),
    )

    assert incident.logs is None
    assert incident.traces is None
    assert incident.validate() == []


def test_rcaeval_converter_produces_canonical_long_format():
    from apex_rca.canonical import rcaeval_metrics_to_canonical

    source = pd.DataFrame({
        "time": [1000, 1060],
        "checkout_cpu": [20.0, 85.0],
        "checkout_memory": [45.0, 48.0],
        "notes": ["normal", "incident"],
    })

    result = rcaeval_metrics_to_canonical(source)

    assert list(result.columns) == ["timestamp", "service", "metric", "value"]
    assert len(result) == 4
    assert set(result["service"]) == {"checkout"}
    assert set(result["metric"]) == {"cpu", "memory"}
    assert set(result["timestamp"]) == {1000, 1060}


def test_rcaeval_converter_does_not_modify_input():
    from apex_rca.canonical import rcaeval_metrics_to_canonical

    source = pd.DataFrame({
        "time": [1000, 1060],
        "checkout_cpu": [20.0, 85.0],
    })
    original = source.copy(deep=True)

    rcaeval_metrics_to_canonical(source)

    pd.testing.assert_frame_equal(source, original)


def test_rcaeval_converter_requires_time_column():
    import pytest
    from apex_rca.canonical import rcaeval_metrics_to_canonical

    with pytest.raises(ValueError, match="time"):
        rcaeval_metrics_to_canonical(pd.DataFrame({"checkout_cpu": [20.0]}))


def test_canonical_wide_round_trip_preserves_rcaeval_metrics():
    from apex_rca.canonical import (
        canonical_metrics_to_wide,
        rcaeval_metrics_to_canonical,
    )

    source = pd.DataFrame({
        "time": [1000, 1060],
        "checkout_cpu": [20.0, 85.0],
        "checkout_memory": [45.0, 48.0],
    })

    canonical = rcaeval_metrics_to_canonical(source)
    wide = canonical_metrics_to_wide(canonical)

    assert set(wide.columns) == set(source.columns)
    pd.testing.assert_frame_equal(
        wide[source.columns],
        source,
        check_dtype=False,
    )


def test_canonical_wide_conversion_rejects_missing_columns():
    import pytest
    from apex_rca.canonical import canonical_metrics_to_wide

    with pytest.raises(ValueError, match="missing required columns"):
        canonical_metrics_to_wide(pd.DataFrame({
            "timestamp": [1000],
            "service": ["checkout"],
        }))


def test_canonical_wide_rejects_duplicate_observations():
    import pytest
    from apex_rca.canonical import canonical_metrics_to_wide

    metrics = pd.DataFrame({
        "timestamp": [1000, 1000],
        "service": ["checkout", "checkout"],
        "metric": ["cpu", "cpu"],
        "value": [20.0, 25.0],
    })

    with pytest.raises(ValueError, match="Duplicate"):
        canonical_metrics_to_wide(metrics)


def test_canonical_wide_rejects_column_name_collisions():
    import pytest
    from apex_rca.canonical import canonical_metrics_to_wide

    metrics = pd.DataFrame({
        "timestamp": [1000, 1000],
        "service": ["api_worker", "api"],
        "metric": ["cpu", "worker_cpu"],
        "value": [20.0, 25.0],
    })

    with pytest.raises(ValueError, match="collide"):
        canonical_metrics_to_wide(metrics)


def test_canonical_incident_rejects_non_finite_metric_values():
    metrics = valid_metrics()
    metrics.loc[0, "value"] = float("inf")

    incident = CanonicalIncident(
        incident_id="test-nonfinite-value",
        dataset="synthetic",
        metrics=metrics,
    )

    assert any("finite" in error for error in incident.validate())


def test_canonical_incident_rejects_non_finite_timestamps():
    metrics = valid_metrics()
    metrics["timestamp"] = metrics["timestamp"].astype(float)
    metrics.loc[0, "timestamp"] = float("inf")

    incident = CanonicalIncident(
        incident_id="test-nonfinite-timestamp",
        dataset="synthetic",
        metrics=metrics,
    )

    assert any("finite" in error for error in incident.validate())


def test_canonical_wide_rejects_non_finite_values():
    import pytest
    from apex_rca.canonical import canonical_metrics_to_wide

    metrics = valid_metrics()
    metrics.loc[0, "value"] = float("inf")

    with pytest.raises(ValueError, match="finite"):
        canonical_metrics_to_wide(metrics)


