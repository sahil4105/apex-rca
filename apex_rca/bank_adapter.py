from pathlib import Path
import pandas as pd

from apex_rca.canonical import CanonicalIncident, DatasetCapabilities
from apex_rca.config import CANONICAL_OBSERVED_SECONDS, CANONICAL_REFERENCE_SECONDS


def load_bank_incident(
    data_dir: str | Path,
    incident_index: int,
    *,
    reference_seconds: float = CANONICAL_REFERENCE_SECONDS,
    observed_seconds: float = CANONICAL_OBSERVED_SECONDS,
    cache_dir: str | Path | None = None,
) -> tuple[CanonicalIncident, dict[str, str]]:
    """Load cached Bank container metrics around an incident timestamp.

    Ground-truth labels are returned separately and never passed to the scorer.
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
    start = incident_time - reference_seconds
    end = incident_time + observed_seconds

    cache = (
        Path(cache_dir)
        if cache_dir is not None
        else Path(__file__).resolve().parents[1] / "results" / "bank_metric_cache"
    )
    if not cache.is_dir():
        raise FileNotFoundError(f"Bank metric cache not found: {cache}")

    frames = []
    for path in sorted(cache.glob("*_container.parquet")):
        # Use Parquet row-group statistics to skip files outside this window.
        parquet = pd.read_parquet(path, columns=["timestamp"])
        if parquet.empty:
            continue
        file_min = pd.to_numeric(parquet["timestamp"], errors="coerce").min()
        file_max = pd.to_numeric(parquet["timestamp"], errors="coerce").max()
        del parquet

        if file_max < start or file_min >= end:
            continue

        raw = pd.read_parquet(
            path,
            columns=["timestamp", "cmdb_id", "kpi_name", "value"],
        )
        raw["timestamp"] = pd.to_numeric(raw["timestamp"], errors="coerce")
        raw = raw.loc[
            raw["timestamp"].ge(start) & raw["timestamp"].lt(end)
        ].copy()
        if raw.empty:
            continue

        raw["timestamp"] = pd.to_numeric(raw["timestamp"], errors="coerce")
        raw["value"] = pd.to_numeric(raw["value"], errors="coerce")
        raw["cmdb_id"] = raw["cmdb_id"].astype("string").str.strip()
        raw["kpi_name"] = raw["kpi_name"].astype("string").str.strip()
        raw = raw.dropna(
            subset=["timestamp", "value", "cmdb_id", "kpi_name"]
        )
        if not raw.empty:
            frames.append(raw)

    if not frames:
        raise ValueError(
            f"No component metrics in the requested window for incident {incident_index}"
        )

    metrics = pd.concat(frames, ignore_index=True).rename(
        columns={"cmdb_id": "service", "kpi_name": "metric"}
    )
    metrics["service"] = metrics["service"].astype(str).str.strip()
    metrics["metric"] = metrics["metric"].astype(str)
    metrics = metrics[["timestamp", "service", "metric", "value"]]
    metrics = metrics.sort_values(
        ["timestamp", "service", "metric"]
    ).reset_index(drop=True)

    incident = CanonicalIncident(
        incident_id=f"bank-{incident_index:03d}",
        dataset="OpenRCA-Bank",
        metrics=metrics,
        incident_time=incident_time,
        description=f"Incident recorded at {record['datetime']}",
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
            "metric_source": "verified Parquet cache",
        },
    )

    errors = incident.validate()
    if errors:
        raise ValueError("Invalid canonical incident: " + "; ".join(errors))

    truth = {
        "component": component,
        "reason": str(record["reason"]),
    }
    return incident, truth



