"""Load RCAEval case index and per-incident telemetry without full-dataset scans."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd


TRACE_GRAPH_COLUMNS = ("spanID", "parentSpanID", "serviceName")
TRACE_EVIDENCE_COLUMNS = (
    "spanID",
    "parentSpanID",
    "serviceName",
    "startTimeMillis",
    "duration",
    "statusCode",
)
LOG_COLUMNS = ("timestamp", "container_name", "message")


@dataclass
class CaseBundle:
    row: pd.Series
    metrics: pd.DataFrame
    logs: pd.DataFrame | None
    traces: pd.DataFrame | None
    logs_available: bool
    traces_available: bool
    logs_loaded: bool
    traces_loaded: bool


def load_index(data_dir: Path) -> pd.DataFrame:
    path = Path(data_dir) / "cases.parquet"
    if not path.exists():
        raise FileNotFoundError(f"Missing dataset index: {path}")
    return pd.read_parquet(path)


def case_dir(data_dir: Path, case_id: str) -> Path:
    return Path(data_dir) / str(case_id)


def load_metrics(data_dir: Path, case_id: str) -> pd.DataFrame:
    path = case_dir(data_dir, case_id) / "metrics.parquet"
    if not path.exists():
        raise FileNotFoundError(f"metrics.parquet missing for {case_id}")
    return pd.read_parquet(path)


def _read_optional(
    path: Path,
    columns: tuple[str, ...] | None = None,
) -> pd.DataFrame | None:
    if not path.exists():
        return None
    try:
        if columns:
            frame = pd.read_parquet(path, columns=list(columns))
        else:
            frame = pd.read_parquet(path)
    except Exception:
        # Column subset may fail if a suite omits a field; retry full schema.
        frame = pd.read_parquet(path)
    return frame


def load_case(
    data_dir: Path,
    row: pd.Series,
    *,
    load_logs: bool = False,
    load_traces: bool = False,
    traces_for_graph_only: bool = False,
) -> CaseBundle:
    case_id = str(row["case"])
    metrics = load_metrics(data_dir, case_id)
    folder = case_dir(data_dir, case_id)

    advertised_logs = bool(row.get("has_logs", False))
    advertised_traces = bool(row.get("has_traces", False))
    logs_path = folder / "logs.parquet"
    traces_path = folder / "traces.parquet"

    logs = None
    traces = None
    if load_logs and (advertised_logs or logs_path.exists()):
        logs = _read_optional(logs_path)
    if load_traces and (advertised_traces or traces_path.exists()):
        cols = TRACE_GRAPH_COLUMNS if traces_for_graph_only else TRACE_EVIDENCE_COLUMNS
        traces = _read_optional(traces_path, cols)

    return CaseBundle(
        row=row,
        metrics=metrics,
        logs=logs,
        traces=traces,
        logs_available=advertised_logs or logs_path.exists(),
        traces_available=advertised_traces or traces_path.exists(),
        logs_loaded=logs is not None,
        traces_loaded=traces is not None,
    )


def index_row(index: pd.DataFrame, case_id: str) -> pd.Series:
    matches = index[index["case"].astype(str) == str(case_id)]
    if matches.empty:
        raise KeyError(f"Unknown case id: {case_id}")
    return matches.iloc[0]


def case_metadata(row: pd.Series) -> dict[str, Any]:
    fields = (
        "case",
        "suite",
        "system",
        "system_name",
        "root_cause_service",
        "fault",
        "fault_description",
        "inject_time",
        "time_start",
        "time_end",
        "normal_timesteps",
        "faulty_timesteps",
        "has_logs",
        "n_logs",
        "has_traces",
        "n_traces",
    )
    return {name: row[name] if name in row.index else None for name in fields}
