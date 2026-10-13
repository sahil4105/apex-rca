"""Dataset-independent data contracts for APEX-RCA."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class DatasetCapabilities:
    """Telemetry and timing features a dataset can reliably provide."""

    metrics: bool = True
    logs: bool = False
    traces: bool = False
    dependency_graph: bool = False
    incident_timestamps: bool = False
    ground_truth: bool = False


@dataclass
class CanonicalIncident:
    """One incident expressed in APEX-RCA's common internal format.

    Timestamps must use Unix seconds. The metrics DataFrame must contain
    a numeric `timestamp` column and a numeric `value` column, alongside
    `service` and `metric` identifiers. Missing modalities remain None.
    """

    incident_id: str
    dataset: str
    metrics: pd.DataFrame
    incident_time: float | None = None
    affected_service: str | None = None
    fault_type: str | None = None
    description: str | None = None
    logs: pd.DataFrame | None = None
    traces: pd.DataFrame | None = None
    topology: list[tuple[str, str]] = field(default_factory=list)
    capabilities: DatasetCapabilities = field(default_factory=DatasetCapabilities)
    metadata: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> list[str]:
        """Return validation errors without modifying or guessing at data."""
        errors: list[str] = []

        required = {"timestamp", "service", "metric", "value"}
        missing = required.difference(self.metrics.columns)
        if missing:
            errors.append(
                "metrics missing required columns: " + ", ".join(sorted(missing))
            )
        else:
            if self.metrics.empty:
                errors.append("metrics contains no rows")
            if not pd.api.types.is_numeric_dtype(self.metrics["timestamp"]):
                errors.append("metrics.timestamp must be numeric Unix seconds")
            if not pd.api.types.is_numeric_dtype(self.metrics["value"]):
                errors.append("metrics.value must be numeric")
            else:
                if not np.isfinite(self.metrics["value"].to_numpy(dtype=float)).all():
                    errors.append("metrics.value must contain only finite values")
            if pd.api.types.is_numeric_dtype(self.metrics["timestamp"]):
                if not np.isfinite(self.metrics["timestamp"].to_numpy(dtype=float)).all():
                    errors.append("metrics.timestamp must contain only finite Unix seconds")
            if self.metrics["service"].isna().any():
                errors.append("metrics.service contains missing values")
            if self.metrics["metric"].isna().any():
                errors.append("metrics.metric contains missing values")
            if not self.metrics["service"].isna().any():
                if self.metrics["service"].astype(str).str.strip().eq("").any():
                    errors.append("metrics.service contains empty identifiers")
            if not self.metrics["metric"].isna().any():
                if self.metrics["metric"].astype(str).str.strip().eq("").any():
                    errors.append("metrics.metric contains empty identifiers")

        if self.incident_time is not None:
            try:
                if not np.isfinite(float(self.incident_time)):
                    errors.append("incident_time must be finite Unix seconds")
            except (TypeError, ValueError, OverflowError):
                errors.append("incident_time must be numeric Unix seconds")

        if self.logs is not None and not isinstance(self.logs, pd.DataFrame):
            errors.append("logs must be a DataFrame or None")
        if self.traces is not None and not isinstance(self.traces, pd.DataFrame):
            errors.append("traces must be a DataFrame or None")

        return errors

def rcaeval_metrics_to_canonical(metrics: pd.DataFrame) -> pd.DataFrame:
    """Convert RCAEval wide-format metrics into canonical long format.

    Output columns: timestamp, service, metric, value.
    The input DataFrame is not modified.
    """
    from apex_rca.metric_parsing import parse_service_metric

    if "time" not in metrics.columns:
        raise ValueError("RCAEval metrics require a 'time' column")

    parsed_columns = []
    for column in metrics.columns:
        parsed = parse_service_metric(str(column))
        if parsed is None:
            continue
        if not pd.api.types.is_numeric_dtype(metrics[column]):
            continue
        service, metric = parsed
        parsed_columns.append((str(column), service, metric))

    if not parsed_columns:
        return pd.DataFrame(
            columns=["timestamp", "service", "metric", "value"]
        )

    frames = []
    for column, service, metric in parsed_columns:
        frames.append(
            pd.DataFrame({
                "timestamp": metrics["time"].to_numpy(copy=True),
                "service": service,
                "metric": metric,
                "value": metrics[column].to_numpy(copy=True),
            })
        )

    result = pd.concat(frames, ignore_index=True)
    result["timestamp"] = pd.to_numeric(result["timestamp"], errors="coerce")
    result["value"] = pd.to_numeric(result["value"], errors="coerce")
    return result


def canonical_metrics_to_wide(metrics: pd.DataFrame) -> pd.DataFrame:
    """Convert canonical long-form metrics into wide format without data loss.

    Requires timestamp, service, metric, and value columns. Duplicate
    observations and ambiguous service/metric column names are rejected.
    """
    required = {"timestamp", "service", "metric", "value"}
    missing = required.difference(metrics.columns)
    if missing:
        raise ValueError(
            "Canonical metrics missing required columns: "
            + ", ".join(sorted(missing))
        )

    frame = metrics[["timestamp", "service", "metric", "value"]].copy()
    frame["timestamp"] = pd.to_numeric(frame["timestamp"], errors="coerce")
    frame["value"] = pd.to_numeric(frame["value"], errors="coerce")

    if frame[["timestamp", "service", "metric", "value"]].isna().any().any():
        raise ValueError("Canonical metrics contain missing or non-numeric values")
    if not np.isfinite(frame["timestamp"].to_numpy(dtype=float)).all():
        raise ValueError("Canonical metric timestamps must be finite")
    if not np.isfinite(frame["value"].to_numpy(dtype=float)).all():
        raise ValueError("Canonical metric values must be finite")

    frame["service"] = frame["service"].astype(str)
    frame["metric"] = frame["metric"].astype(str)

    if (frame["service"].str.len() == 0).any() or (frame["metric"].str.len() == 0).any():
        raise ValueError("Service and metric identifiers must not be empty")

    keys = ["timestamp", "service", "metric"]
    if frame.duplicated(keys).any():
        raise ValueError(
            "Duplicate timestamp/service/metric observations; aggregate them "
            "explicitly in the dataset adapter if aggregation is justified"
        )

    frame["column"] = frame["service"] + "_" + frame["metric"]
    pairs = frame[["column", "service", "metric"]].drop_duplicates()
    if pairs["column"].duplicated().any():
        raise ValueError(
            "Service/metric names collide when converted to wide columns; "
            "the dataset adapter must provide unambiguous identifiers"
        )

    if frame.empty:
        return pd.DataFrame(columns=["time"])

    wide = frame.pivot(
        index="timestamp",
        columns="column",
        values="value",
    )
    wide.columns.name = None
    wide.index.name = "time"
    return wide.reset_index().sort_values("time").reset_index(drop=True)
