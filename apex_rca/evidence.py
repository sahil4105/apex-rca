"""Evidence-grounded explanations from scores that were actually computed."""

from __future__ import annotations

from typing import Any

from apex_rca.dependency_graph import DependencyGraph


def explain_service(
    service: str,
    *,
    metric_details: dict[str, list[tuple[str, float]]],
    metric_scores: dict[str, float],
    graph: DependencyGraph | None,
    graph_scores: dict[str, float],
    log_scores: dict[str, float],
    trace_scores: dict[str, float],
    logs_available: bool,
    traces_available: bool,
    top_metrics: int = 3,
) -> dict[str, Any]:
    reasons: list[str] = []
    effects = metric_details.get(service, [])
    metric_score = metric_scores.get(service)
    if metric_score is not None:
        reasons.append(
            f"Metric anomaly score {metric_score:.3f} (mean of strongest {min(top_metrics, len(effects))} signals)."
        )
    for column, value in effects[:top_metrics]:
        reasons.append(f"Metric {column} robust effect {value:.3f}.")
    if not effects:
        reasons.append("No usable metric-change evidence for this service.")

    if graph is not None and graph.n_edges > 0:
        callers = sorted(graph.graph.predecessors(service)) if graph.graph.has_node(service) else []
        callees = sorted(graph.graph.successors(service)) if graph.graph.has_node(service) else []
        reasons.append(
            f"Graph provenance={graph.provenance}; callers={callers[:8]}; callees={callees[:8]}."
        )
        if service in graph_scores:
            reasons.append(f"Personalized PageRank mass {graph_scores[service]:.4f}.")
    elif graph is not None:
        reasons.append(f"No dependency edges used (provenance={graph.provenance}).")

    if service in log_scores:
        reasons.append(f"Log error-rate increase score {log_scores[service]:.3f}.")
    elif not logs_available:
        reasons.append("Logs unavailable for this case; log evidence was not used.")
    else:
        reasons.append("No log error-rate increase recorded for this service.")

    if service in trace_scores:
        reasons.append(f"Trace duration/status evidence score {trace_scores[service]:.3f}.")
    elif not traces_available:
        reasons.append("Traces unavailable for this case; trace evidence was not used.")
    else:
        reasons.append("No trace duration/status evidence recorded for this service.")

    return {
        "service": service,
        "reasons": reasons,
        "metric_effects": effects[:top_metrics],
        "metric_score": metric_score,
        "graph_score": graph_scores.get(service),
        "log_score": log_scores.get(service),
        "trace_score": trace_scores.get(service),
    }
