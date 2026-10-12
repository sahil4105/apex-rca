"""Temporal windowing and numeric cleaning for retrospective diagnosis."""

from __future__ import annotations

from typing import Any

import pandas as pd


def coerce_unix_seconds(series: pd.Series) -> pd.Series:
    """Best-effort conversion of mixed timestamp encodings to Unix seconds."""
    values = pd.to_numeric(series, errors="coerce")
    if values.notna().any():
        sample = float(values.dropna().iloc[0])
        # Microseconds around 1e15, milliseconds around 1e12.
        if sample > 1e14:
            values = values / 1e6
        elif sample > 1e11:
            values = values / 1e3
    return values


def split_by_inject_time(
    df: pd.DataFrame,
    inject_time: float,
    time_col: str = "time",
    *,
    time_start: float | None = None,
    time_end: float | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split telemetry into a pre-injection reference and post-injection window.

    This implements *retrospective incident diagnosis*: both windows are taken
    from the recorded case, and the post-injection rows are observed after the
    fault timestamp. It is not a real-time / causal forecasting protocol.
    """
    if time_col not in df.columns:
        raise KeyError(f"Missing time column: {time_col}")
    ordered = df.sort_values(time_col)
    if time_start is not None:
        ordered = ordered[ordered[time_col] >= float(time_start)]
    if time_end is not None:
        ordered = ordered[ordered[time_col] < float(time_end)]
    stamp = float(inject_time)
    reference = ordered[ordered[time_col] < stamp]
    observed = ordered[ordered[time_col] >= stamp]
    return reference, observed


def inject_in_recorded_window(row: Any) -> bool:
    """Return True if inject_time lies within [time_start, time_end]."""
    try:
        inject = float(row["inject_time"])
        start = float(row["time_start"])
        end = float(row["time_end"])
    except (KeyError, TypeError, ValueError):
        return False
    return start <= inject <= end
