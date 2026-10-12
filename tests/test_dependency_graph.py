import pandas as pd

from apex_rca.anomaly_scoring import minmax_normalize
from apex_rca.dependency_graph import build_dependency_graph, traces_to_edges
from apex_rca.ranking import combine_anomaly_and_graph, rank_services


def test_parent_child_edges_not_all_pairs():
    traces = pd.DataFrame(
        {
            "spanID": ["s1", "s2", "s3"],
            "parentSpanID": [None, "s1", "s1"],
            "serviceName": ["frontend", "adservice", "cartservice"],
        }
    )
    edges = traces_to_edges(traces, min_count=1)
    assert ("frontend", "adservice") in edges
    assert ("frontend", "cartservice") in edges
    assert ("adservice", "cartservice") not in edges


def test_frontend_trace_alias():
    traces = pd.DataFrame(
        {
            "spanID": ["a", "b"],
            "parentSpanID": [None, "a"],
            "serviceName": ["frontendservice", "adservice"],
        }
    )
    edges = traces_to_edges(traces, min_count=1)
    assert ("frontend", "adservice") in edges


def test_canonical_fallback_when_traces_missing():
    dep = build_dependency_graph(
        system_name="Online Boutique",
        traces=None,
        services=["frontend", "adservice", "cartservice"],
        mode="auto",
    )
    assert dep.provenance == "canonical_system_graph"
    assert dep.graph.has_edge("frontend", "adservice")


def test_train_ticket_without_traces_has_no_fabricated_graph():
    dep = build_dependency_graph(
        system_name="Train Ticket",
        traces=None,
        services=["ts-auth-service", "ts-order-service"],
        mode="auto",
    )
    assert dep.provenance == "none"
    assert dep.n_edges == 0


def test_trace_parent_child_requires_matching_span_id():
    traces = pd.DataFrame(
        {
            "spanID": ["child"],
            "parentSpanID": ["missing-parent"],
            "serviceName": ["adservice"],
        }
    )
    assert traces_to_edges(traces, min_count=1) == {}


def test_combine_and_rank_prefers_graph_when_weighted():
    anomaly = {"symptom": 10.0, "root": 1.0}
    graph = {"symptom": 0.1, "root": 0.9}
    mixed = combine_anomaly_and_graph(anomaly, graph, graph_weight=1.0)
    ranked = rank_services(mixed)
    assert ranked[0][0] == "root"
    assert minmax_normalize({"a": 1, "b": 3})["b"] == 1.0
