"""Combine anomaly scores with optional graph and extra-telemetry evidence."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from apex_rca.anomaly_scoring import minmax_normalize


def merge_scores(
    metric_scores: Mapping[str, float],
    extras: Sequence[Mapping[str, float]],
    *,
    extra_weight: float,
) -> dict[str, float]:
    """Add scaled extra evidence only for services that actually have it."""
    combined = {name: float(score) for name, score in metric_scores.items()}
    if extra_weight <= 0:
        return combined
    extra_union: dict[str, list[float]] = {}
    for mapping in extras:
        for name, value in mapping.items():
            extra_union.setdefault(name, []).append(float(value))
    for name, values in extra_union.items():
        extra = sum(values) / len(values)
        combined[name] = combined.get(name, 0.0) + extra_weight * extra
    return combined


def combine_anomaly_and_graph(
    anomaly_scores: Mapping[str, float],
    graph_scores: Mapping[str, float],
    *,
    graph_weight: float,
) -> dict[str, float]:
    """Convex combination of min-max normalized anomaly and PageRank scores.

    S(s) = (1-λ) Â(s) + λ π̂(s)

    If the graph score map is empty, the ranking is identical to the
    (already aggregated) anomaly scores.
    """
    if not anomaly_scores:
        return {}
    if not graph_scores or graph_weight <= 0:
        return dict(anomaly_scores)

    a_hat = minmax_normalize(dict(anomaly_scores))
    g_hat = minmax_normalize({key: graph_scores.get(key, 0.0) for key in anomaly_scores})
    lambd = min(max(float(graph_weight), 0.0), 1.0)
    return {
        name: (1.0 - lambd) * a_hat[name] + lambd * g_hat.get(name, 0.0)
        for name in anomaly_scores
    }


def rank_services(scores: Mapping[str, float]) -> list[tuple[str, float]]:
    return sorted(scores.items(), key=lambda item: (-item[1], item[0]))
