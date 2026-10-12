"""Small, interpretable log and trace evidence features.

Missing logs or traces contribute nothing. Absence is not treated as health.
"""

from __future__ import annotations

import re

import pandas as pd

from apex_rca.config import MIN_WINDOW_SAMPLES
from apex_rca.anomaly_scoring import anomaly_effect
from apex_rca.metric_parsing import normalize_service_name
from apex_rca.preprocessing import coerce_unix_seconds

ERROR_PATTERN = re.compile(
    r"error|exception|fail|timeout|fatal|panic|refused|unavailable|traceback| 5\d\d",
    re.IGNORECASE,
)


def _filter_window(frame: pd.DataFrame, time_col: str, start: float, end: float) -> pd.DataFrame:
    if frame is None or frame.empty or time_col not in frame.columns:
        return pd.DataFrame()
    stamps = coerce_unix_seconds(frame[time_col])
    mask = (stamps >= start) & (stamps < end)
    return frame.loc[mask]


def log_error_scores(
    logs: pd.DataFrame | None,
    *,
    inject_time: float,
    time_start: float,
    time_end: float,
    services: list[str],
) -> dict[str, float]:
    """Post-minus-pre error-like log rate, scaled to a comparable magnitude."""
    if logs is None or logs.empty:
        return {}
    if "container_name" not in logs.columns or "message" not in logs.columns:
        return {}
    if "timestamp" not in logs.columns:
        return {}

    reference = _filter_window(logs, "timestamp", time_start, inject_time)
    observed = _filter_window(logs, "timestamp", inject_time, time_end)
    if reference.empty and observed.empty:
        return {}

    known = set(services)
    scores: dict[str, float] = {}

    
    def _with_service(frame: pd.DataFrame) -> pd.DataFrame:
        out = frame.copy()
        if "_svc" not in out.columns:
            if "container_name" in out.columns:
                out["_svc"] = out["container_name"].map(normalize_service_name)
            else:
                out["_svc"] = pd.Series(dtype=object, index=out.index)
        return out


    reference = _with_service(reference)
    observed = _with_service(observed)
    names = pd.concat(
        [
            reference["_svc"] if not reference.empty else pd.Series(dtype=object),
            observed["_svc"] if not observed.empty else pd.Series(dtype=object),
        ],
        ignore_index=True,
    ).dropna().unique()

    for raw_name in names:
        service = str(raw_name)
        if service not in known:
            continue
        ref = reference[reference["_svc"] == service]
        obs = observed[observed["_svc"] == service]
        ref_n = max(len(ref), 1)
        obs_n = max(len(obs), 1)
        ref_err = 0
        obs_err = 0
        if "message" in ref.columns and not ref.empty:
            ref_err = int(ref["message"].astype(str).str.contains(ERROR_PATTERN, na=False).sum())
        if "message" in obs.columns and not obs.empty:
            obs_err = int(obs["message"].astype(str).str.contains(ERROR_PATTERN, na=False).sum())
        delta = (obs_err / obs_n) - (ref_err / ref_n)
        if delta > 0:
            scores[service] = float(min(delta * 20.0, 20.0))
    return scores


def trace_evidence_scores(
    traces: pd.DataFrame | None,
    *,
    inject_time: float,
    time_start: float,
    time_end: float,
    services: list[str],
    min_samples: int = MIN_WINDOW_SAMPLES,
) -> dict[str, float]:
    """Duration shift plus non-OK status-rate increase, averaged when both exist."""
    if traces is None or traces.empty or "serviceName" not in traces.columns:
        return {}

    time_col = "startTimeMillis" if "startTimeMillis" in traces.columns else None
    if time_col is None:
        return {}

    work = traces.copy()
    work["_t"] = coerce_unix_seconds(work[time_col])
    work["_svc"] = work["serviceName"].map(normalize_service_name)
    reference = work[(work["_t"] >= time_start) & (work["_t"] < inject_time)]
    observed = work[(work["_t"] >= inject_time) & (work["_t"] < time_end)]
    known = set(services)
    scores: dict[str, float] = {}

    for service in sorted(set(work["_svc"].dropna().astype(str))):
        if service not in known:
            continue
        ref = reference[reference["_svc"] == service]
        obs = observed[observed["_svc"] == service]
        parts: list[float] = []

        if "duration" in work.columns and len(ref) >= min_samples and len(obs) >= min_samples:
            effect = anomaly_effect(
                pd.to_numeric(ref["duration"], errors="coerce").to_numpy(),
                pd.to_numeric(obs["duration"], errors="coerce").to_numpy(),
                min_samples=min_samples,
            )
            if effect is not None:
                parts.append(effect)

        if "statusCode" in work.columns and (len(ref) + len(obs)) > 0:
            def _bad_rate(frame: pd.DataFrame) -> float:
                if frame.empty or "statusCode" not in frame.columns:
                    return 0.0
                status = pd.to_numeric(frame["statusCode"], errors="coerce")
                known_status = status.dropna()
                if known_status.empty:
                    return 0.0
                return float((known_status != 0).mean())

            delta = _bad_rate(obs) - _bad_rate(ref)
            if delta > 0:
                parts.append(float(min(delta * 20.0, 20.0)))

        if parts:
            scores[service] = float(sum(parts) / len(parts))
    return scores
