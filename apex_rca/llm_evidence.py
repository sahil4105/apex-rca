"""Evidence selection and packaging for LLM-based root-cause diagnosis."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Literal

import pandas as pd

from apex_rca.data_loader import CaseBundle
from apex_rca.logs_traces import ERROR_PATTERN
from apex_rca.metric_parsing import normalize_service_name
from apex_rca.pipeline import CaseResult
from apex_rca.preprocessing import coerce_unix_seconds

MethodVariant = Literal["raw_logs", "anomaly_only", "topology_anomaly"]


@dataclass
class EvidenceItem:
    """A discrete unit of evidence with a stable identifier and provenance."""

    id: str
    service: str
    modality: Literal["metric", "topology", "log", "trace", "status"]
    description: str
    provenance: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "service": self.service,
            "modality": self.modality,
            "description": self.description,
            "provenance": self.provenance,
        }


@dataclass
class EvidencePackage:
    """Complete evidence bundle supplied to the LLM prompt."""

    case_id: str
    system: str
    method_variant: MethodVariant
    candidate_services: list[str]
    candidate_ranks: dict[str, int]
    candidate_scores: dict[str, float]
    items: list[EvidenceItem] = field(default_factory=list)
    raw_logs_sample: list[str] = field(default_factory=list)
    raw_logs_truncated: bool = False
    total_log_lines_found: int = 0
    modalities_available: dict[str, bool] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    @property
    def valid_evidence_ids(self) -> set[str]:
        return {item.id for item in self.items}

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "system": self.system,
            "method_variant": self.method_variant,
            "candidate_services": self.candidate_services,
            "candidate_ranks": self.candidate_ranks,
            "candidate_scores": self.candidate_scores,
            "items": [item.to_dict() for item in self.items],
            "raw_logs_sample": self.raw_logs_sample,
            "raw_logs_truncated": self.raw_logs_truncated,
            "total_log_lines_found": self.total_log_lines_found,
            "modalities_available": self.modalities_available,
            "notes": self.notes,
        }

    def format_for_prompt(self) -> str:
        """Render evidence package into clean, grounded text for the prompt."""
        lines = [
            f"=== INCIDENT CONTEXT ===",
            f"Case: {self.case_id}",
            f"System: {self.system}",
            f"Diagnostic Variant: {self.method_variant}",
            f"Available Telemetry: " + ", ".join(
                f"{k}={'yes' if v else 'no'}" for k, v in self.modalities_available.items()
            ),
            "",
            f"=== CANDIDATE SERVICES (TOP RANKED) ===",
        ]
        for svc in self.candidate_services:
            rank = self.candidate_ranks.get(svc, "n/a")
            score = self.candidate_scores.get(svc, 0.0)
            lines.append(f"- Service: {svc} (Upstream rank: #{rank}, score: {score:.3f})")

        if self.notes:
            lines.append("")
            lines.append("=== SYSTEM NOTES ===")
            for note in self.notes:
                lines.append(f"- {note}")

        if self.method_variant == "raw_logs":
            lines.append("")
            lines.append("=== RAW LOGS (SAMPLED AROUND INCIDENT) ===")
            if not self.raw_logs_sample:
                lines.append("No raw log lines available for this incident.")
            else:
                for log_line in self.raw_logs_sample:
                    lines.append(log_line)
                if self.raw_logs_truncated:
                    lines.append(
                        f"[NOTE: Truncated to {len(self.raw_logs_sample)} lines out of "
                        f"{self.total_log_lines_found} total available lines]"
                    )
        else:
            lines.append("")
            lines.append("=== STRUCTURED EVIDENCE ITEMS ===")
            if not self.items:
                lines.append("No structured evidence items extracted.")
            else:
                for item in self.items:
                    lines.append(
                        f"[{item.id}] (Service: {item.service}, Modality: {item.modality}): "
                        f"{item.description}"
                    )

        return "\n".join(lines)


def sample_raw_logs(
    logs: pd.DataFrame | None,
    *,
    inject_time: float,
    window_before_s: float = 60.0,
    window_after_s: float = 120.0,
    max_lines: int = 50,
) -> tuple[list[str], bool, int]:
    """Sample raw logs around inject_time with prioritized error extraction.

    Policy:
    - Filters logs to [inject_time - window_before_s, inject_time + window_after_s].
    - Prioritizes lines matching ERROR_PATTERN (errors, exceptions, status 5xx).
    - Fills remaining capacity with chronological ambient logs.
    - Caps output at max_lines.
    """
    if logs is None or logs.empty or "timestamp" not in logs.columns or "message" not in logs.columns:
        return [], False, 0

    stamps = coerce_unix_seconds(logs["timestamp"])
    start = inject_time - window_before_s
    end = inject_time + window_after_s
    mask = (stamps >= start) & (stamps < end)
    window_df = logs.loc[mask]

    total_lines = len(window_df)
    if total_lines == 0:
        return [], False, 0

    has_container = "container_name" in window_df.columns

    def format_row(row: pd.Series) -> str:
        container = f"[{row['container_name']}] " if has_container else ""
        return f"{row['timestamp']}: {container}{str(row['message'])[:160]}"

    error_mask = window_df["message"].astype(str).str.contains(ERROR_PATTERN)
    error_rows = window_df.loc[error_mask]
    other_rows = window_df.loc[~error_mask]

    selected_lines: list[str] = []
    for _, row in error_rows.head(max_lines).iterrows():
        selected_lines.append(format_row(row))

    remaining = max_lines - len(selected_lines)
    if remaining > 0:
        for _, row in other_rows.head(remaining).iterrows():
            selected_lines.append(format_row(row))

    truncated = total_lines > len(selected_lines)
    return selected_lines, truncated, total_lines


def build_evidence_package(
    bundle: CaseBundle,
    result: CaseResult,
    method_variant: MethodVariant,
    *,
    candidate_k: int = 3,
    oracle_service: str | None = None,
    max_raw_log_lines: int = 50,
    top_metrics_per_service: int = 3,
) -> EvidencePackage:
    """Build a grounded evidence package for the top candidate services.

    Ground-truth labels (fault, true root cause) are NEVER passed into this function
    or the prompt package. If oracle_service is set, it is used solely as an evaluation
    control candidate to inspect ranking-error propagation.
    """
    case_id = result.case
    system = result.system

    # Select candidates from upstream ranking
    ranked_tuples = list(result.ranked)
    candidate_services = [svc for svc, _ in ranked_tuples[:candidate_k]]
    candidate_ranks = {svc: idx + 1 for idx, (svc, _) in enumerate(ranked_tuples[:candidate_k])}
    candidate_scores = {svc: score for svc, score in ranked_tuples[:candidate_k]}

    # If oracle candidate is specified and not in top-k, inject it explicitly as control
    if oracle_service and oracle_service not in candidate_services:
        candidate_services.append(oracle_service)
        found_rank = None
        found_score = 0.0
        for idx, (svc, score) in enumerate(ranked_tuples):
            if svc == oracle_service:
                found_rank = idx + 1
                found_score = score
                break
        candidate_ranks[oracle_service] = found_rank if found_rank is not None else 999
        candidate_scores[oracle_service] = found_score

    modalities = {
        "metrics": True,
        "logs": bool(bundle.logs_available),
        "traces": bool(bundle.traces_available),
        "dependency_graph": (
            method_variant == "topology_anomaly" and result.graph_provenance != "unused"
        ),
    }

    notes: list[str] = []
    if not bundle.logs_available:
        notes.append("Application logs were not recorded for this incident.")
    if not bundle.traces_available:
        notes.append("Distributed traces were not recorded for this incident.")

    # 1. Variant A: Raw Logs
    if method_variant == "raw_logs":
        inject_time = float(bundle.row.get("inject_time", 0.0))
        sample_lines, truncated, total = sample_raw_logs(
            bundle.logs if bundle.logs_loaded else None,
            inject_time=inject_time,
            max_lines=max_raw_log_lines,
        )
        return EvidencePackage(
            case_id=case_id,
            system=system,
            method_variant="raw_logs",
            candidate_services=candidate_services,
            candidate_ranks=candidate_ranks,
            candidate_scores=candidate_scores,
            items=[],
            raw_logs_sample=sample_lines,
            raw_logs_truncated=truncated,
            total_log_lines_found=total,
            modalities_available=modalities,
            notes=notes,
        )

    # 2. Variants B & C: Structured Evidence Items
    items: list[EvidenceItem] = []
    counter = 1

    extras = result.extras
    explanations_by_svc = {
        exp["service"]: exp for exp in extras.get("explanations", []) if "service" in exp
    }
    metric_scores = extras.get("metric_scores", {})
    graph_scores = extras.get("graph_scores", {})
    log_scores = extras.get("log_scores", {})
    trace_scores = extras.get("trace_scores", {})

    for svc in candidate_services:
        exp = explanations_by_svc.get(svc, {})
        m_score = metric_scores.get(svc, exp.get("metric_score"))
        effects = exp.get("metric_effects", [])

        # Metric evidence
        if m_score is not None:
            top_effects = effects[:top_metrics_per_service]
            effects_desc = (
                ", ".join(f"{col} (effect {val:.2f})" for col, val in top_effects)
                if top_effects
                else "no specific metric columns recorded"
            )
            items.append(
                EvidenceItem(
                    id=f"EVID-METRIC-{counter:02d}",
                    service=svc,
                    modality="metric",
                    description=(
                        f"Overall metric anomaly score {m_score:.3f}. "
                        f"Strongest metric deviations: {effects_desc}."
                    ),
                    provenance={
                        "metric_score": float(m_score),
                        "top_effects": top_effects,
                    },
                )
            )
            counter += 1

        # Log evidence (if available)
        l_score = log_scores.get(svc, exp.get("log_score"))
        if l_score is not None and l_score > 0.0:
            items.append(
                EvidenceItem(
                    id=f"EVID-LOG-{counter:02d}",
                    service=svc,
                    modality="log",
                    description=f"Log error-rate increase score {l_score:.3f} detected around injection time.",
                    provenance={"log_score": float(l_score)},
                )
            )
            counter += 1
        elif not bundle.logs_available:
            pass  # recorded in package notes
        else:
            items.append(
                EvidenceItem(
                    id=f"EVID-LOG-{counter:02d}",
                    service=svc,
                    modality="log",
                    description="No elevated log error rate recorded for this service.",
                    provenance={"log_score": 0.0},
                )
            )
            counter += 1

        # Trace evidence (if available)
        t_score = trace_scores.get(svc, exp.get("trace_score"))
        if t_score is not None and t_score > 0.0:
            items.append(
                EvidenceItem(
                    id=f"EVID-TRACE-{counter:02d}",
                    service=svc,
                    modality="trace",
                    description=f"Trace duration/status anomaly score {t_score:.3f} recorded.",
                    provenance={"trace_score": float(t_score)},
                )
            )
            counter += 1

        # 3. Topology evidence (ONLY for Variant C)
        if method_variant == "topology_anomaly":
            g_score = graph_scores.get(svc, exp.get("graph_score"))
            # Search for caller/callee relations in reasons or graph_notes
            topo_reasons = [r for r in exp.get("reasons", []) if "callers=" in r or "Graph provenance=" in r]
            topo_desc = "; ".join(topo_reasons) if topo_reasons else f"Dependency node in system topology."
            if g_score is not None:
                topo_desc += f" Personalized PageRank topological centrality: {g_score:.4f}."

            items.append(
                EvidenceItem(
                    id=f"EVID-TOPO-{counter:02d}",
                    service=svc,
                    modality="topology",
                    description=topo_desc,
                    provenance={
                        "graph_score": float(g_score) if g_score is not None else None,
                        "graph_provenance": result.graph_provenance,
                    },
                )
            )
            counter += 1

    return EvidencePackage(
        case_id=case_id,
        system=system,
        method_variant=method_variant,
        candidate_services=candidate_services,
        candidate_ranks=candidate_ranks,
        candidate_scores=candidate_scores,
        items=items,
        raw_logs_sample=[],
        raw_logs_truncated=False,
        total_log_lines_found=0,
        modalities_available=modalities,
        notes=notes,
    )

