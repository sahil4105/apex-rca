"""Experiment configuration and documented defaults.

The default graph weight and extra-telemetry weight are a priori choices,
not the result of a label-driven grid search on RCAEval.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


METRIC_SUFFIXES: tuple[str, ...] = (
    "latency-50",
    "latency-90",
    "diskio",
    "workload",
    "socket",
    "latency",
    "error",
    "memory",
    "cpu",
    "mem",
    "load",
)

# Trace service names that differ from metric column prefixes.
SERVICE_ALIASES: dict[str, str] = {
    "frontendservice": "frontend",
    "frontend-service": "frontend",
    "frontend_service": "frontend",
}

MIN_WINDOW_SAMPLES = 30
ANOMALY_EFFECT_CAP = 20.0
TOP_K_METRICS = 3
CANONICAL_REFERENCE_SECONDS = 1800
CANONICAL_OBSERVED_SECONDS = 1800
RANDOM_SEED = 42


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def default_rcaeval_dir() -> Path:
    return project_root() / "data" / "rcaeval"


def default_results_dir() -> Path:
    return project_root() / "results"


@dataclass
class ExperimentConfig:
    """Serializable settings stored alongside experiment outputs."""

    name: str = "rcaeval"
    version: str = "apex_rca_v1"
    data_dir: str = field(default_factory=lambda: str(default_rcaeval_dir()))
    results_dir: str = field(default_factory=lambda: str(default_results_dir()))
    min_window_samples: int = MIN_WINDOW_SAMPLES
    anomaly_effect_cap: float = ANOMALY_EFFECT_CAP
    top_k_metrics: int = TOP_K_METRICS
    graph_weight: float = 0.30
    extra_weight: float = 0.25
    pagerank_damping: float = 0.85
    min_trace_edge_count: int = 3
    graph_mode: str = "auto"  # auto | traces | canonical | union | none
    graph_time_scope: str = "full_recorded_case_trace"
    seed: int = RANDOM_SEED
    task: str = "retrospective_post_injection_diagnosis"
    created_at_utc: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

