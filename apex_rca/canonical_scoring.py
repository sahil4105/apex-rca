"""Dataset-independent anomaly scoring for canonical metric observations."""

from __future__ import annotations

import pandas as pd

from apex_rca.anomaly_scoring import score_services_from_windows
from apex_rca.config import (
    ANOMALY_EFFECT_CAP,
    CANONICAL_OBSERVED_SECONDS,
    CANONICAL_REFERENCE_SECONDS,
    MIN_WINDOW_SAMPLES,
    TOP_K_METRICS,
)


def score_canonical_incident(
    metrics: pd.DataFrame,
    incident_time: float,
    *,
    reference_seconds: float = CANONICAL_REFERENCE_SECONDS,
    observed_seconds: float = CANONICAL_OBSERVED_SECONDS,
    min_samples: int = MIN_WINDOW_SAMPLES,
    cap: float = ANOMALY_EFFECT_CAP,
    top_k_metrics: int = TOP_K_METRICS,
) -> tuple[dict[str, float], dict[str, list[tuple[str, float]]]]:
    """Score services from canonical metrics around a known incident time.

    Input metrics must contain timestamp, service, metric, and value columns.
    Timestamps are Unix seconds. Each service/metric series is converted into
    an explicit wide column, so scoring does not depend on dataset-specific
    metric naming conventions.

    The reference window is [incident_time - reference_seconds, incident_time).
    The observed window is [incident_time, incident_time + observed_seconds).
    Ground truth is not accepted by this function and is never used for scoring.
    """
    required = {"timestamp", "service", "metric", "value"}
    missing = required.difference(metrics.columns)
    if missing:
        raise ValueError(
            "Canonical metrics missing required columns: "
            + ", ".join(sorted(missing))
        )

    if metrics.empty:
        raise ValueError("Canonical metrics contain no rows")

    try:
        stamp = float(incident_time)
    except (TypeError, ValueError) as exc:
        raise ValueError("incident_time must be numeric Unix seconds") from exc

    if not pd.notna(stamp) or not pd.Series([stamp]).map(
        lambda value: abs(value) != float("inf")
    ).iloc[0]:
        raise ValueError("incident_time must be finite Unix seconds")

    if reference_seconds <= 0 or observed_seconds <= 0:
        raise ValueError("Window durations must be positive")
    if min_samples < 1 or top_k_metrics < 1:
        raise ValueError("min_samples and top_k_metrics must be positive")

    frame = metrics[["timestamp", "service", "metric", "value"]].copy()
    frame["timestamp"] = pd.to_numeric(frame["timestamp"], errors="coerce")
    frame["value"] = pd.to_numeric(frame["value"], errors="coerce")

    if frame[["timestamp", "service", "metric", "value"]].isna().any().any():
        raise ValueError("Canonical metrics contain missing or non-numeric values")

    frame["service"] = frame["service"].astype(str)
    frame["metric"] = frame["metric"].astype(str)

    if not frame["timestamp"].map(lambda value: abs(value) != float("inf")).all():
        raise ValueError("Metric timestamps must be finite Unix seconds")
    if not frame["value"].map(lambda value: abs(value) != float("inf")).all():
        raise ValueError("Metric values must be finite")

    frame = frame[
        (frame["timestamp"] >= stamp - reference_seconds)
        & (frame["timestamp"] < stamp + observed_seconds)
    ].copy()

    if frame.empty:
        raise ValueError("No metric observations in the requested time windows")

    duplicate_keys = frame.duplicated(
        subset=["timestamp", "service", "metric"],
        keep=False,
    )
    if duplicate_keys.any():
        examples = (
            frame.loc[duplicate_keys, ["timestamp", "service", "metric"]]
            .drop_duplicates()
            .head(5)
            .to_dict(orient="records")
        )
        raise ValueError(
            "Duplicate canonical observations for (timestamp, service, metric). "
            f"Examples: {examples}"
        )

    # Create internal column IDs to avoid collisions in arbitrary dataset names.
    pairs = (
        frame[["service", "metric"]]
        .drop_duplicates()
        .sort_values(["service", "metric"])
        .reset_index(drop=True)
    )
    pairs["column"] = [f"__metric_{i}" for i in range(len(pairs))]
    frame = frame.merge(pairs, on=["service", "metric"], how="left", validate="many_to_one")

    wide = frame.pivot(
        index="timestamp",
        columns="column",
        values="value",
    )
    wide.columns.name = None
    wide.index.name = "time"
    wide = wide.reset_index().sort_values("time").reset_index(drop=True)

    mapping: dict[str, list[str]] = {}
    for service, group in pairs.groupby("service", sort=True):
        mapping[str(service)] = group["column"].tolist()

    reference = wide[
        (wide["time"] >= stamp - reference_seconds) & (wide["time"] < stamp)
    ].drop(columns=["time"])
    observed = wide[
        (wide["time"] >= stamp) & (wide["time"] < stamp + observed_seconds)
    ].drop(columns=["time"])

    scores, internal_details = score_services_from_windows(
        reference,
        observed,
        mapping,
        min_samples=min_samples,
        cap=cap,
        top_k_metrics=top_k_metrics,
    )

    display_names = dict(zip(pairs["column"], pairs["metric"]))
    details = {
        service: [(display_names[column], effect) for column, effect in effects]
        for service, effects in internal_details.items()
    }
    return scores, details

