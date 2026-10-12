"""Robust metric-change scoring.

The functions ``anomaly_effect`` and ``score_services_from_windows`` reproduce
the original ``experiments/baseline_rcaeval.py`` method (version ``anomaly_only_v1``):
median shift relative to a MAD-based scale, capped, then the mean of the
strongest three metric effects per service.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from apex_rca.config import ANOMALY_EFFECT_CAP, MIN_WINDOW_SAMPLES, TOP_K_METRICS
from apex_rca.metric_parsing import service_metric_columns


def anomaly_effect(
    reference: np.ndarray,
    observed: np.ndarray,
    *,
    min_samples: int = MIN_WINDOW_SAMPLES,
    cap: float = ANOMALY_EFFECT_CAP,
) -> float | None:
    """Robust, capped effect size for a change in a metric."""
    reference = np.asarray(reference, dtype=float)
    observed = np.asarray(observed, dtype=float)

    reference = reference[np.isfinite(reference)]
    observed = observed[np.isfinite(observed)]

    if len(reference) < min_samples or len(observed) < min_samples:
        return None

    ref_median = np.median(reference)
    obs_median = np.median(observed)

    mad = np.median(np.abs(reference - ref_median))
    scale = 1.4826 * mad

    if not np.isfinite(scale) or scale < 1e-12:
        scale = np.std(reference)

    if not np.isfinite(scale) or scale < 1e-12:
        scale = max(abs(ref_median) * 0.01, 1e-6)

    effect = abs(obs_median - ref_median) / scale
    return float(min(effect, cap))


def score_services_from_windows(
    reference: pd.DataFrame,
    observed: pd.DataFrame,
    mapping: dict[str, list[str]] | None = None,
    *,
    min_samples: int = MIN_WINDOW_SAMPLES,
    cap: float = ANOMALY_EFFECT_CAP,
    top_k_metrics: int = TOP_K_METRICS,
) -> tuple[dict[str, float], dict[str, list[tuple[str, float]]]]:
    """Return per-service scores and the metric effects used to compute them."""
    if mapping is None:
        mapping = service_metric_columns(observed if not observed.empty else reference)

    scores: dict[str, float] = {}
    details: dict[str, list[tuple[str, float]]] = {}

    for service, columns in mapping.items():
        effects: list[tuple[str, float]] = []
        for col in columns:
            if col not in reference.columns or col not in observed.columns:
                continue
            effect = anomaly_effect(
                reference[col].to_numpy(),
                observed[col].to_numpy(),
                min_samples=min_samples,
                cap=cap,
            )
            if effect is not None:
                effects.append((col, effect))
        if not effects:
            continue
        effects.sort(key=lambda item: item[1], reverse=True)
        strongest = effects[:top_k_metrics]
        scores[service] = float(np.mean([value for _, value in strongest]))
        details[service] = effects

    return scores, details


def minmax_normalize(scores: dict[str, float]) -> dict[str, float]:
    """Scale scores to [0, 1] within a case. Constant maps stay at 0."""
    if not scores:
        return {}
    values = np.array(list(scores.values()), dtype=float)
    lo, hi = float(np.min(values)), float(np.max(values))
    if not np.isfinite(lo) or not np.isfinite(hi) or hi - lo < 1e-12:
        return {key: 0.0 for key in scores}
    return {key: float((val - lo) / (hi - lo)) for key, val in scores.items()}
