import pytest

from apex_rca.ranking import (
    combine_anomaly_and_graph,
    merge_scores,
    rank_services,
)


def test_merge_scores_averages_available_evidence():
    result = merge_scores(
        {"api": 2.0, "db": 1.0},
        [{"api": 4.0}, {"api": 2.0, "cache": 3.0}],
        extra_weight=0.5,
    )

    assert result == {
        "api": 3.5,   # 2.0 + 0.5 * mean(4.0, 2.0)
        "db": 1.0,
        "cache": 1.5,  # 0.0 + 0.5 * 3.0
    }


def test_merge_scores_with_no_extras_preserves_metric_scores():
    metrics = {"api": 2.0, "db": 1.0}

    assert merge_scores(metrics, [], extra_weight=0.5) == metrics


@pytest.mark.parametrize("weight", [0.0, -0.5])
def test_merge_scores_nonpositive_weight_ignores_extras(weight):
    metrics = {"api": 2.0, "db": 1.0}

    assert merge_scores(
        metrics, [{"api": 100.0}], extra_weight=weight
    ) == metrics


def test_combine_graph_empty_or_zero_weight_preserves_anomaly_scores():
    anomaly = {"api": 8.0, "db": 2.0}

    assert combine_anomaly_and_graph(
        anomaly, {}, graph_weight=0.3
    ) == anomaly
    assert combine_anomaly_and_graph(
        anomaly, {"db": 1.0}, graph_weight=0.0
    ) == anomaly


def test_graph_weight_one_uses_normalized_graph_scores():
    result = combine_anomaly_and_graph(
        {"api": 10.0, "db": 0.0, "cache": 5.0},
        {"api": 0.0, "db": 10.0, "cache": 5.0},
        graph_weight=1.0,
    )

    assert result == {"api": 0.0, "db": 1.0, "cache": 0.5}


def test_graph_weight_is_clamped_to_valid_range():
    anomaly = {"api": 10.0, "db": 0.0}
    graph = {"api": 0.0, "db": 10.0}

    assert combine_anomaly_and_graph(
        anomaly, graph, graph_weight=-1.0
    ) == anomaly

    assert combine_anomaly_and_graph(
        anomaly, graph, graph_weight=2.0
    ) == combine_anomaly_and_graph(
        anomaly, graph, graph_weight=1.0
    )


def test_missing_graph_services_receive_zero_graph_score():
    result = combine_anomaly_and_graph(
        {"api": 10.0, "db": 0.0},
        {"api": 1.0},
        graph_weight=1.0,
    )

    assert result == {"api": 1.0, "db": 0.0}


def test_empty_anomaly_scores_return_empty_result():
    assert combine_anomaly_and_graph(
        {}, {"api": 1.0}, graph_weight=0.3
    ) == {}


def test_constant_scores_normalize_without_nonfinite_values():
    result = combine_anomaly_and_graph(
        {"api": 3.0, "db": 3.0},
        {"api": 5.0, "db": 5.0},
        graph_weight=0.3,
    )

    assert result == {"api": 0.0, "db": 0.0}


def test_rank_services_sorts_by_score_then_name():
    assert rank_services(
        {"zeta": 0.8, "beta": 0.8, "alpha": 0.9}
    ) == [
        ("alpha", 0.9),
        ("beta", 0.8),
        ("zeta", 0.8),
    ]


def test_rank_services_is_deterministic_for_ties():
    first = rank_services({"zeta": 1.0, "beta": 1.0})
    second = rank_services({"beta": 1.0, "zeta": 1.0})

    assert first == second == [("beta", 1.0), ("zeta", 1.0)]
