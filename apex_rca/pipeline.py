"""End-to-end RCA ranking for a single RCAEval case."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import pandas as pd

from apex_rca.anomaly_scoring import score_services_from_windows
from apex_rca.config import ExperimentConfig
from apex_rca.data_loader import CaseBundle, load_case
from apex_rca.dependency_graph import (
    DependencyGraph,
    build_dependency_graph,
    pagerank_from_anomaly,
)
from apex_rca.evaluation import case_metrics
from apex_rca.evidence import explain_service
from apex_rca.logs_traces import log_error_scores, trace_evidence_scores
from apex_rca.metric_parsing import service_metric_columns
from apex_rca.preprocessing import inject_in_recorded_window, split_by_inject_time
from apex_rca.ranking import combine_anomaly_and_graph, merge_scores, rank_services

MethodName = Literal[
    "anomaly_only",
    "metrics_graph",
    "metrics_logs_traces",
    "full",
]


@dataclass
class CaseResult:
    case: str
    method: str
    suite: str
    system: str
    fault: str
    root_cause: str
    ranked: list[tuple[str, float]]
    hit1: int
    hit3: int
    hit5: int
    mrr: float
    rank: int | None
    graph_provenance: str
    skip_reason: str | None = None
    runtime_s: float = 0.0
    extras: dict[str, Any] = field(default_factory=dict)

    def to_row(self) -> dict[str, Any]:
        top3 = ", ".join(f"{name} ({score:.2f})" for name, score in self.ranked[:3])
        return {
            "case": self.case,
            "method": self.method,
            "suite": self.suite,
            "system": self.system,
            "fault": self.fault,
            "root_cause": self.root_cause,
            "hit1": self.hit1,
            "hit3": self.hit3,
            "hit5": self.hit5,
            "mrr": self.mrr,
            "rank": self.rank,
            "graph_provenance": self.graph_provenance,
            "n_candidates": len(self.ranked),
            "root_cause_in_candidates": (
                int(self.root_cause in [name for name, _ in self.ranked])
                if self.root_cause
                else 0
            ),
            "runtime_s": self.runtime_s,
            "top3": top3,
            "ranked_names": "|".join(name for name, _ in self.ranked),
        }


def _needs_logs(method: str) -> bool:
    return method in {"metrics_logs_traces", "full"}


def _needs_traces_evidence(method: str) -> bool:
    return method in {"metrics_logs_traces", "full"}


def _needs_graph(method: str) -> bool:
    return method in {"metrics_graph", "full"}


def diagnose_case(
    bundle: CaseBundle,
    config: ExperimentConfig,
    method: MethodName = "anomaly_only",
) -> CaseResult:
    started = time.perf_counter()
    row = bundle.row
    case = str(row["case"])
    suite = str(row.get("suite", ""))
    system = str(row.get("system_name", row.get("system", "")))
    fault = str(row.get("fault", ""))
    truth = str(row.get("root_cause_service", "")).strip()

    def skipped(reason: str) -> CaseResult:
        return CaseResult(
            case=case,
            method=method,
            suite=suite,
            system=system,
            fault=fault,
            root_cause=truth,
            ranked=[],
            hit1=0,
            hit3=0,
            hit5=0,
            mrr=0.0,
            rank=None,
            graph_provenance="n/a",
            skip_reason=reason,
            runtime_s=time.perf_counter() - started,
        )

    metrics = bundle.metrics
    if "time" not in metrics.columns:
        return skipped("time column missing")
    if "inject_time" not in row.index or pd.isna(row["inject_time"]):
        return skipped("injection timestamp missing")

    inject_time = float(row["inject_time"])
    if not inject_in_recorded_window(row):
        # Keep these cases skipped rather than inventing a corrected timestamp.
        return skipped("inject_time outside recorded [time_start, time_end] window")

    time_start = float(row.get("time_start", metrics["time"].min()))
    time_end = float(row.get("time_end", metrics["time"].max()))
    reference, observed = split_by_inject_time(
        metrics,
        inject_time,
        time_start=time_start,
        time_end=time_end,
    )
    min_samples = config.min_window_samples
    if len(reference) < min_samples or len(observed) < min_samples:
        return skipped("insufficient pre/post-injection samples")

    mapping = service_metric_columns(metrics)
    metric_scores, metric_details = score_services_from_windows(
        reference,
        observed,
        mapping,
        min_samples=min_samples,
        cap=config.anomaly_effect_cap,
        top_k_metrics=config.top_k_metrics,
    )
    if not metric_scores:
        return skipped("no usable service metrics")

    services = list(metric_scores)
    log_scores: dict[str, float] = {}
    trace_scores: dict[str, float] = {}
    if _needs_logs(method) and bundle.logs_loaded:
        log_scores = log_error_scores(
            bundle.logs,
            inject_time=inject_time,
            time_start=time_start,
            time_end=time_end,
            services=services,
        )
    if _needs_traces_evidence(method) and bundle.traces_loaded:
        trace_scores = trace_evidence_scores(
            bundle.traces,
            inject_time=inject_time,
            time_start=time_start,
            time_end=time_end,
            services=services,
            min_samples=min_samples,
        )

    extras = []
    if _needs_logs(method) or _needs_traces_evidence(method):
        extras = [log_scores, trace_scores]
    anomaly_for_rank = merge_scores(
        metric_scores,
        extras,
        extra_weight=config.extra_weight if extras else 0.0,
    )

    graph: DependencyGraph | None = None
    graph_scores: dict[str, float] = {}
    provenance = "none"
    if _needs_graph(method):
        graph_start: float | None = time_start
        graph_end: float | None = time_end
        if config.graph_time_scope == "pre_injection_only":
            graph_end = inject_time
        elif config.graph_time_scope == "observation_only":
            graph_start = inject_time

        graph = build_dependency_graph(
            system_name=system,
            traces=bundle.traces if bundle.traces_loaded else None,
            services=services,
            mode=config.graph_mode,
            min_trace_edge_count=config.min_trace_edge_count,
            time_start=graph_start,
            time_end=graph_end,
        )
        provenance = graph.provenance
        graph_scores = pagerank_from_anomaly(
            graph,
            anomaly_for_rank,
            damping=config.pagerank_damping,
        )
        final_scores = combine_anomaly_and_graph(
            anomaly_for_rank,
            graph_scores,
            graph_weight=config.graph_weight,
        )
    else:
        final_scores = anomaly_for_rank
        provenance = "unused"

    ranked = rank_services(final_scores)
    names = [name for name, _ in ranked]
    metrics_eval = case_metrics(names, truth)
    explanations = [
        explain_service(
            name,
            metric_details=metric_details,
            metric_scores=metric_scores,
            graph=graph,
            graph_scores=graph_scores,
            log_scores=log_scores,
            trace_scores=trace_scores,
            logs_available=bundle.logs_available,
            traces_available=bundle.traces_available,
        )
        for name, _ in ranked[:5]
    ]

    return CaseResult(
        case=case,
        method=method,
        suite=suite,
        system=system,
        fault=fault,
        root_cause=truth,
        ranked=ranked,
        hit1=int(metrics_eval["hit1"]),
        hit3=int(metrics_eval["hit3"]),
        hit5=int(metrics_eval["hit5"]),
        mrr=float(metrics_eval["mrr"]),
        rank=metrics_eval["rank"],
        graph_provenance=provenance,
        runtime_s=time.perf_counter() - started,
        extras={
            "explanations": explanations,
            "metric_scores": metric_scores,
            "graph_scores": graph_scores,
            "log_scores": log_scores,
            "trace_scores": trace_scores,
            "logs_available": bundle.logs_available,
            "traces_available": bundle.traces_available,
            "n_reference": int(len(reference)),
            "n_observed": int(len(observed)),
            "inject_time": inject_time,
            "graph_notes": graph.notes if graph is not None else [],
            "graph_n_edges": graph.n_edges if graph is not None else 0,
        },
    )


def run_case(
    data_dir: Path,
    row: pd.Series,
    config: ExperimentConfig,
    method: MethodName = "anomaly_only",
) -> CaseResult:
    load_logs = _needs_logs(method)
    load_traces = _needs_graph(method) or _needs_traces_evidence(method)
    traces_for_graph_only = _needs_graph(method) and not _needs_traces_evidence(method)
    try:
        bundle = load_case(
            data_dir,
            row,
            load_logs=load_logs,
            load_traces=load_traces,
            traces_for_graph_only=traces_for_graph_only,
        )
    except FileNotFoundError as exc:
        started = time.perf_counter()
        return CaseResult(
            case=str(row.get("case", "")),
            method=method,
            suite=str(row.get("suite", "")),
            system=str(row.get("system_name", row.get("system", ""))),
            fault=str(row.get("fault", "")),
            root_cause=str(row.get("root_cause_service", "")).strip(),
            ranked=[],
            hit1=0,
            hit3=0,
            hit5=0,
            mrr=0.0,
            rank=None,
            graph_provenance="n/a",
            skip_reason=str(exc),
            runtime_s=time.perf_counter() - started,
        )
    return diagnose_case(bundle, config, method)
