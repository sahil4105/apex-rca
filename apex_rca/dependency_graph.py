"""Build directed caller-callee graphs and graph-aware ranking scores.

Parent-child span joins are the only trace-derived edges. Co-occurrence of
two services in the same trace is *not* treated as a dependency.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import networkx as nx
import pandas as pd

from apex_rca.metric_parsing import normalize_service_name
from apex_rca.preprocessing import coerce_unix_seconds
from apex_rca.topologies import canonical_edges


@dataclass
class DependencyGraph:
    graph: nx.DiGraph
    provenance: str
    edge_counts: dict[tuple[str, str], int] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    @property
    def n_nodes(self) -> int:
        return int(self.graph.number_of_nodes())

    @property
    def n_edges(self) -> int:
        return int(self.graph.number_of_edges())


def traces_to_edges(
    traces: pd.DataFrame,
    *,
    min_count: int = 3,
    time_start: float | None = None,
    time_end: float | None = None,
    time_col: str = "startTimeMillis",
) -> dict[tuple[str, str], int]:
    """Derive caller -> callee counts from parent/child spans with temporal boundaries.

    When time_start and/or time_end are provided, filters spans strictly to [time_start, time_end).
    When traceID is present, joins spans within the same trace to prevent spanID collisions.
    """
    required = {"spanID", "parentSpanID", "serviceName"}
    if traces is None or traces.empty or not required.issubset(traces.columns):
        return {}

    work = traces
    if (time_start is not None or time_end is not None) and time_col in traces.columns:
        stamps = coerce_unix_seconds(traces[time_col])
        mask = pd.Series(True, index=traces.index)
        if time_start is not None:
            mask &= stamps >= float(time_start)
        if time_end is not None:
            mask &= stamps < float(time_end)
        work = traces.loc[mask]
        if work.empty:
            return {}

    cols = list(required)
    has_trace_id = "traceID" in work.columns
    if has_trace_id:
        cols.append("traceID")

    spans = work.loc[:, cols].dropna(subset=["spanID", "serviceName"])
    if spans.empty:
        return {}

    spans = spans.copy()
    spans["serviceName"] = spans["serviceName"].map(normalize_service_name)

    if has_trace_id:
        parents = (
            spans[["traceID", "spanID", "serviceName"]]
            .drop_duplicates(subset=["traceID", "spanID"])
            .rename(columns={"spanID": "parentSpanID", "serviceName": "caller"})
        )
        children = spans.dropna(subset=["parentSpanID"]).rename(
            columns={"serviceName": "callee"}
        )
        merged = children.merge(
            parents, on=["traceID", "parentSpanID"], how="inner"
        )
    else:
        parents = (
            spans[["spanID", "serviceName"]]
            .drop_duplicates(subset=["spanID"])
            .rename(columns={"spanID": "parentSpanID", "serviceName": "caller"})
        )
        children = spans.dropna(subset=["parentSpanID"]).rename(
            columns={"serviceName": "callee"}
        )
        merged = children.merge(parents, on="parentSpanID", how="inner")

    merged = merged[merged["caller"].astype(str) != merged["callee"].astype(str)]
    if merged.empty:
        return {}

    counts = (
        merged.groupby(["caller", "callee"], sort=False)
        .size()
        .reset_index(name="n")
    )
    edges: dict[tuple[str, str], int] = {}
    for _, row in counts.iterrows():
        if int(row["n"]) < min_count:
            continue
        edges[(str(row["caller"]), str(row["callee"]))] = int(row["n"])
    return edges


def build_dependency_graph(
    *,
    system_name: str,
    traces: pd.DataFrame | None,
    services: list[str],
    mode: str = "auto",
    min_trace_edge_count: int = 3,
    time_start: float | None = None,
    time_end: float | None = None,
) -> DependencyGraph:
    """Construct a directed graph and record how the edges were obtained."""
    notes: list[str] = []
    canonical = {(src, dst): 1 for src, dst in canonical_edges(system_name)}
    trace_edges: dict[tuple[str, str], int] = {}
    if traces is not None and not traces.empty:
        trace_edges = traces_to_edges(
            traces,
            min_count=min_trace_edge_count,
            time_start=time_start,
            time_end=time_end,
        )
    elif traces is None:
        notes.append("traces_unavailable")

    mode = (mode or "auto").lower()
    if mode == "none":
        selected: dict[tuple[str, str], int] = {}
        provenance = "none"
    elif mode == "canonical":
        selected = dict(canonical)
        provenance = "canonical_system_graph" if canonical else "none"
        if not canonical:
            notes.append("no_canonical_graph_for_system")
    elif mode == "traces":
        selected = dict(trace_edges)
        provenance = "trace_parent_child" if trace_edges else "none"
        if not trace_edges:
            notes.append("no_trace_edges")
    elif mode == "union":
        selected = dict(canonical)
        selected.update(trace_edges)
        if canonical and trace_edges:
            provenance = "canonical_union_trace_parent_child"
        elif trace_edges:
            provenance = "trace_parent_child"
        elif canonical:
            provenance = "canonical_system_graph"
        else:
            provenance = "none"
    else:
        # auto: prefer traces; otherwise canonical; otherwise empty.
        if trace_edges:
            selected = dict(trace_edges)
            provenance = "trace_parent_child"
        elif canonical:
            selected = dict(canonical)
            provenance = "canonical_system_graph"
            notes.append("trace_fallback_canonical")
        else:
            selected = {}
            provenance = "none"
            notes.append("no_graph_available")

    graph = nx.DiGraph()
    graph.add_nodes_from(services)
    for (src, dst), count in selected.items():
        graph.add_edge(src, dst, weight=float(count))
        graph.add_node(src)
        graph.add_node(dst)

    if graph.number_of_edges() == 0:
        provenance = "none"
        notes.append("empty_edge_set")

    return DependencyGraph(
        graph=graph,
        provenance=provenance,
        edge_counts=selected,
        notes=notes,
    )


def pagerank_from_anomaly(
    dep: DependencyGraph,
    anomaly_scores: dict[str, float],
    *,
    damping: float = 0.85,
) -> dict[str, float]:
    """Personalized PageRank on caller→callee edges.

    Anomalous callers spread mass toward the callees they depend on, which
    is the intended direction for localizing a fault that surfaces upstream.
    Isolated nodes keep only their personalization mass.
    """
    graph = dep.graph
    if graph.number_of_nodes() == 0:
        return {}

    total = sum(max(float(v), 0.0) for v in anomaly_scores.values())
    if total <= 0:
        personalization = {node: 1.0 / graph.number_of_nodes() for node in graph.nodes}
    else:
        personalization = {}
        for node in graph.nodes:
            personalization[node] = max(float(anomaly_scores.get(node, 0.0)), 0.0) / total
        leftover = [node for node, val in personalization.items() if val == 0]
        if leftover and sum(personalization.values()) <= 0:
            personalization = {
                node: 1.0 / graph.number_of_nodes() for node in graph.nodes
            }

    try:
        ranks = nx.pagerank(
            graph,
            alpha=damping,
            personalization=personalization,
            weight="weight",
        )
    except nx.PowerIterationFailedConvergence:
        return {node: float(anomaly_scores.get(node, 0.0)) for node in graph.nodes}
    return {node: float(value) for node, value in ranks.items()}
