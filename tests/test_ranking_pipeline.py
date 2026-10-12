import pandas as pd

from apex_rca.config import ExperimentConfig
from apex_rca.data_loader import CaseBundle
from apex_rca.pipeline import diagnose_case


def _synthetic_bundle(inject: int = 40) -> CaseBundle:
    times = list(range(80))
    metrics = pd.DataFrame(
        {
            "time": times,
            "adservice_cpu": [1.0] * inject + [10.0] * (80 - inject),
            "frontend_cpu": [1.0] * inject + [2.0] * (80 - inject),
        }
    )
    row = pd.Series(
        {
            "case": "synthetic_adservice_cpu_1",
            "suite": "SYN",
            "system_name": "Online Boutique",
            "fault": "cpu",
            "root_cause_service": "adservice",
            "inject_time": inject,
            "time_start": 0,
            "time_end": 79,
            "has_logs": False,
            "has_traces": False,
        }
    )
    return CaseBundle(
        row=row,
        metrics=metrics,
        logs=None,
        traces=None,
        logs_available=False,
        traces_available=False,
        logs_loaded=False,
        traces_loaded=False,
    )


def test_anomaly_only_ranks_shifted_service_first():
    result = diagnose_case(_synthetic_bundle(), ExperimentConfig(), "anomaly_only")
    assert result.skip_reason is None
    assert result.ranked[0][0] == "adservice"
    assert result.hit1 == 1


def test_graph_method_runs_with_canonical_fallback():
    result = diagnose_case(_synthetic_bundle(), ExperimentConfig(), "metrics_graph")
    assert result.skip_reason is None
    assert result.graph_provenance == "canonical_system_graph"
    assert result.ranked[0][0] == "adservice"


def test_out_of_window_inject_is_skipped():
    bundle = _synthetic_bundle()
    bundle.row["inject_time"] = 10_000
    result = diagnose_case(bundle, ExperimentConfig(), "anomaly_only")
    assert result.skip_reason is not None
    assert "window" in result.skip_reason


def test_metric_end_boundary_is_excluded_from_observation():
    bundle = _synthetic_bundle()
    bundle.metrics.loc[79, "adservice_cpu"] = 1000.0
    bundle.row["time_end"] = 79
    result = diagnose_case(bundle, ExperimentConfig(), "anomaly_only")
    assert result.skip_reason is None
    assert result.extras["n_observed"] == 39
