import pandas as pd

from apex_rca.logs_traces import log_error_scores
from apex_rca.preprocessing import split_by_inject_time


def test_split_by_inject_time_uses_half_open_case_window():
    frame = pd.DataFrame({"time": [-1, 0, 9, 10, 19, 20]})
    reference, observed = split_by_inject_time(
        frame,
        inject_time=10,
        time_start=0,
        time_end=20,
    )
    assert reference["time"].tolist() == [0, 9]
    assert observed["time"].tolist() == [10, 19]


def test_log_evidence_excludes_case_end_timestamp():
    logs = pd.DataFrame(
        {
            "timestamp": [5, 15, 20],
            "container_name": ["api", "api", "api"],
            "message": ["ok", "ok", "error"],
        }
    )
    scores = log_error_scores(
        logs,
        inject_time=10,
        time_start=0,
        time_end=20,
        services=["api"],
    )
    assert scores == {}
