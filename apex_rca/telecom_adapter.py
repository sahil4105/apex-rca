from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from apex_rca.canonical import CanonicalIncident, DatasetCapabilities
from apex_rca.config import CANONICAL_OBSERVED_SECONDS, CANONICAL_REFERENCE_SECONDS


INFRASTRUCTURE_FILES = (
    "metric_container.csv",
    "metric_middleware.csv",
    "metric_node.csv",
    "metric_service.csv",
)



def deduplicate_exact_source_rows(frame: pd.DataFrame) -> pd.DataFrame:
    """Remove only completely identical source rows; preserve conflicts."""
    return frame.drop_duplicates().copy()


def load_telecom_incident(
    data_dir: str | Path,
    incident_index: int,
    *,
    reference_seconds: float = CANONICAL_REFERENCE_SECONDS,
    observed_seconds: float = CANONICAL_OBSERVED_SECONDS,
) -> tuple[CanonicalIncident, dict[str, str]]:
    """Load one Telecom incident using infrastructure metrics only.

    Source metric timestamps are milliseconds and are normalized to Unix seconds.
    Infrastructure series retain itemid in the canonical metric identifier so
    observations with different item IDs are not silently merged.

    Ground-truth labels are returned separately and never passed to the scorer.
    Application metrics are excluded because duplicate service/timestamp rows
    have unresolved aggregation semantics.
    """
    folder = Path(data_dir)
    records = pd.read_csv(folder / "record.csv")

    if incident_index < 0 or incident_index >= len(records):
        raise IndexError(
            f"incident_index must be between 0 and {len(records) - 1}"
        )
    if reference_seconds <= 0 or observed_seconds <= 0:
        raise ValueError("Window durations must be positive")

    record = records.iloc[incident_index]
    component = str(record["component"]).strip()
    incident_time = float(record["timestamp"])

    if not np.isfinite(incident_time):
        raise ValueError(f"Invalid incident timestamp at index {incident_index}")

    start = incident_time - reference_seconds
    end = incident_time + observed_seconds
    day = pd.to_datetime(str(record["datetime"]), errors="raise").strftime("%Y_%m_%d")
    metric_dir = folder / "telemetry" / day / "metric"

    frames: list[pd.DataFrame] = []
    categories_found: list[str] = []

    for filename in INFRASTRUCTURE_FILES:
        path = metric_dir / filename
        if not path.is_file():
            continue

        raw = pd.read_csv(
            path,
            usecols=["timestamp", "value", "cmdb_id", "name", "itemid"],
        )
        raw["timestamp"] = pd.to_numeric(raw["timestamp"], errors="coerce") / 1000.0
        raw["value"] = pd.to_numeric(raw["value"], errors="coerce")
        raw["cmdb_id"] = raw["cmdb_id"].astype("string").str.strip()
        raw["name"] = raw["name"].astype("string").str.strip()
        raw["itemid"] = raw["itemid"].astype("string").str.strip()

        raw = raw.loc[
            raw["timestamp"].ge(start)
            & raw["timestamp"].lt(end)
        ].copy()
        raw = raw.dropna(
            subset=["timestamp", "value", "cmdb_id", "name", "itemid"]
        )
        raw = deduplicate_exact_source_rows(raw)

        if raw.empty:
            continue

        if not np.isfinite(raw["timestamp"].to_numpy(dtype=float)).all():
            raise ValueError(f"Non-finite timestamps in {path}")
        if not np.isfinite(raw["value"].to_numpy(dtype=float)).all():
            raise ValueError(f"Non-finite metric values in {path}")

        raw["service"] = raw["cmdb_id"].astype(str)
        raw["metric"] = (
            filename.removeprefix("metric_").removesuffix(".csv")
            + "::"
            + raw["name"].astype(str)
            + "::itemid="
            + raw["itemid"].astype(str)
        )
        frames.append(raw[["timestamp", "service", "metric", "value"]])
        categories_found.append(filename.removeprefix("metric_").removesuffix(".csv"))

    if not frames:
        raise ValueError(
            f"No infrastructure metrics in the requested time window "
            f"for Telecom incident {incident_index}"
        )

    metrics = pd.concat(frames, ignore_index=True)

    # Conflicting observations at the same canonical key have no reliable
    # ordering or aggregation rule. Exclude all values at those keys rather
    # than choosing or averaging values arbitrarily.
    canonical_keys = ["timestamp", "service", "metric"]
    conflicting = (
        metrics.groupby(canonical_keys, dropna=False)["value"]
        .nunique(dropna=False)
        .gt(1)
    )
    conflicting_keys = conflicting[conflicting].index

    conflict_key_count = len(conflicting_keys)
    conflict_observation_count = 0

    if conflict_key_count:
        key_index = pd.MultiIndex.from_frame(metrics[canonical_keys])
        conflict_mask = key_index.isin(conflicting_keys)
        conflict_observation_count = int(conflict_mask.sum())
        metrics = metrics.loc[~conflict_mask].copy()

    metrics = metrics.sort_values(
        ["timestamp", "service", "metric"]
    ).reset_index(drop=True)

    if metrics.empty:
        raise ValueError(
            f"No unambiguous infrastructure metrics remain for "
            f"Telecom incident {incident_index}"
        )

    incident = CanonicalIncident(
        incident_id=f"telecom-{incident_index:03d}",
        dataset="OpenRCA-Telecom",
        metrics=metrics,
        incident_time=incident_time,
        description=f"Recorded incident at {record['datetime']}",
        capabilities=DatasetCapabilities(
            metrics=True,
            incident_timestamps=True,
            ground_truth=True,
        ),
        metadata={
            "source_row_index": int(incident_index),
            "recorded_level": str(record["level"]),
            "recorded_datetime": str(record["datetime"]),
            "reference_seconds": float(reference_seconds),
            "observed_seconds": float(observed_seconds),
            "metric_categories": sorted(set(categories_found)),
            "application_metrics_included": False,
            "metric_timestamp_conversion": "milliseconds_to_unix_seconds",
            "conflict_policy": "exclude_all_observations_at_conflicting_canonical_keys",
            "conflicting_canonical_keys_excluded": int(conflict_key_count),
            "conflicting_observations_excluded": int(conflict_observation_count),
        },
    )

    errors = incident.validate()
    if errors:
        raise ValueError("Invalid canonical incident: " + "; ".join(errors))

    truth = {
        "component": component,
        "reason": str(record["reason"]),
        "level": str(record["level"]),
    }
    return incident, truth
