from apex_rca.metric_parsing import (
    normalize_service_name,
    parse_service_metric,
    service_metric_columns,
)
import pandas as pd


def test_longest_suffix_wins_for_latency_quantiles():
    assert parse_service_metric("carts_latency-50") == ("carts", "latency-50")
    assert parse_service_metric("carts_latency-90") == ("carts", "latency-90")
    assert parse_service_metric("carts_latency") == ("carts", "latency")


def test_hyphenated_service_names():
    assert parse_service_metric("front-end_cpu") == ("front-end", "cpu")
    assert parse_service_metric("ts-auth-service_mem") == ("ts-auth-service", "mem")


def test_non_metric_columns_ignored():
    assert parse_service_metric("time") is None
    assert parse_service_metric("inject_time") is None


def test_service_metric_columns_numeric_only():
    df = pd.DataFrame(
        {
            "time": [1, 2],
            "adservice_cpu": [0.1, 0.2],
            "adservice_mem": [1.0, 1.1],
            "frontend_latency": [3.0, 4.0],
            "notes": ["a", "b"],
        }
    )
    mapping = service_metric_columns(df)
    assert set(mapping) == {"adservice", "frontend"}
    assert mapping["adservice"] == ["adservice_cpu", "adservice_mem"]


def test_frontend_alias():
    assert normalize_service_name("frontendservice") == "frontend"
    assert normalize_service_name("adservice") == "adservice"
