import numpy as np
import pandas as pd

from apex_rca.anomaly_scoring import anomaly_effect, score_services_from_windows


def test_anomaly_effect_detects_level_shift():
    reference = np.ones(40)
    observed = np.full(40, 10.0)
    effect = anomaly_effect(reference, observed)
    assert effect is not None
    assert effect == 20.0  # capped


def test_anomaly_effect_rejects_short_windows():
    assert anomaly_effect(np.ones(10), np.ones(40)) is None


def test_constant_metric_fallback_scale():
    reference = np.full(40, 5.0)
    observed = np.full(40, 6.0)
    effect = anomaly_effect(reference, observed)
    assert effect is not None
    assert effect > 0


def test_nan_and_inf_are_dropped():
    reference = np.array([1.0] * 40 + [np.nan, np.inf])
    observed = np.array([2.0] * 40 + [-np.inf])
    effect = anomaly_effect(reference, observed)
    assert effect is not None


def test_service_score_uses_top_three_mean():
    index = range(40)
    reference = pd.DataFrame(
        {
            "svc_cpu": np.ones(40),
            "svc_mem": np.ones(40),
            "svc_latency": np.ones(40),
            "svc_error": np.ones(40),
        },
        index=index,
    )
    observed = pd.DataFrame(
        {
            "svc_cpu": np.full(40, 10.0),
            "svc_mem": np.full(40, 10.0),
            "svc_latency": np.full(40, 10.0),
            "svc_error": np.ones(40),
        },
        index=index,
    )
    mapping = {
        "svc": ["svc_cpu", "svc_mem", "svc_latency", "svc_error"],
    }
    scores, details = score_services_from_windows(reference, observed, mapping)
    assert "svc" in scores
    effects = [value for _, value in details["svc"]]
    strongest = sorted(effects, reverse=True)[:3]
    assert scores["svc"] == np.mean(strongest)
