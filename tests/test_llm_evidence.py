from pathlib import Path
import pandas as pd
import pytest

from apex_rca.data_loader import CaseBundle
from apex_rca.llm_evidence import (
    EvidenceItem,
    EvidencePackage,
    build_evidence_package,
    sample_raw_logs,
)
from apex_rca.pipeline import CaseResult


def test_sample_raw_logs_prioritizes_errors_and_truncates():
    logs = pd.DataFrame({
        "timestamp": [100, 105, 110, 115, 120, 125, 200],
        "container_name": ["order", "cart", "payment", "order", "cart", "payment", "order"],
        "message": [
            "info: starting request",
            "info: cart loaded",
            "ERROR: payment gateway timed out",
            "info: retry attempt",
            "fatal: connection refused",
            "info: transaction complete",
            "info: outside window",
        ],
    })

    # inject_time = 110, window [110-20, 110+20] -> [90, 130] -> includes 100, 105, 110, 115, 120, 125
    lines, truncated, total = sample_raw_logs(
        logs,
        inject_time=110,
        window_before_s=20,
        window_after_s=20,
        max_lines=2,
    )

    assert total == 6
    assert truncated is True
    assert len(lines) == 2
    # The two error/fatal lines should be prioritized:
    assert any("ERROR" in line for line in lines)
    assert any("fatal" in line for line in lines)


def test_build_evidence_package_variants():
    row = pd.Series({
        "case": "test_case_01",
        "system": "online_boutique",
        "inject_time": 1000.0,
    })
    bundle = CaseBundle(
        row=row,
        metrics=pd.DataFrame({"time": [900, 1000, 1100], "frontend_cpu": [10, 20, 90]}),
        logs=None,
        traces=None,
        logs_available=False,
        traces_available=False,
        logs_loaded=False,
        traces_loaded=False,
    )
    result = CaseResult(
        case="test_case_01",
        method="metrics_graph",
        suite="re1",
        system="online_boutique",
        fault="cpu_spike",
        root_cause="frontend",
        ranked=[("frontend", 0.9), ("cartservice", 0.5), ("paymentservice", 0.3), ("redis", 0.1)],
        hit1=1,
        hit3=1,
        hit5=1,
        mrr=1.0,
        rank=1,
        graph_provenance="static",
        extras={
            "metric_scores": {"frontend": 0.85, "cartservice": 0.4},
            "graph_scores": {"frontend": 0.35, "cartservice": 0.2},
            "explanations": [
                {
                    "service": "frontend",
                    "metric_score": 0.85,
                    "metric_effects": [("frontend_cpu", 4.2)],
                    "reasons": ["callers=[]; callees=['cartservice']"],
                },
                {
                    "service": "cartservice",
                    "metric_score": 0.4,
                    "metric_effects": [("cart_cpu", 1.2)],
                    "reasons": ["callers=['frontend']; callees=[]"],
                },
            ],
        },
    )

    # Test Anomaly-only variant
    pkg_b = build_evidence_package(bundle, result, method_variant="anomaly_only", candidate_k=2)
    assert pkg_b.candidate_services == ["frontend", "cartservice"]
    assert len(pkg_b.candidate_services) == 2
    # Should contain METRIC items, but NO TOPO items
    assert all("TOPO" not in item.id for item in pkg_b.items)
    assert any("METRIC" in item.id for item in pkg_b.items)

    # Test Topology+Anomaly variant
    pkg_c = build_evidence_package(bundle, result, method_variant="topology_anomaly", candidate_k=2)
    assert any("TOPO" in item.id for item in pkg_c.items)
    topo_items = [it for it in pkg_c.items if it.modality == "topology"]
    assert len(topo_items) == 2

    # Test Oracle candidate injection
    pkg_oracle = build_evidence_package(
        bundle, result, method_variant="topology_anomaly", candidate_k=1, oracle_service="redis"
    )
    # top 1 was frontend, but oracle added redis
    assert "frontend" in pkg_oracle.candidate_services
    assert "redis" in pkg_oracle.candidate_services


def test_evidence_package_missing_modalities_notes():
    row = pd.Series({"case": "test_02", "inject_time": 500.0})
    bundle = CaseBundle(
        row=row,
        metrics=pd.DataFrame(),
        logs=None,
        traces=None,
        logs_available=False,
        traces_available=False,
        logs_loaded=False,
        traces_loaded=False,
    )
    result = CaseResult(
        case="test_02",
        method="anomaly_only",
        suite="re1",
        system="sock_shop",
        fault="none",
        root_cause="orders",
        ranked=[("orders", 0.8)],
        hit1=1,
        hit3=1,
        hit5=1,
        mrr=1.0,
        rank=1,
        graph_provenance="none",
        extras={},
    )
    pkg = build_evidence_package(bundle, result, method_variant="anomaly_only")
    assert any("logs were not recorded" in n.lower() for n in pkg.notes)
    assert any("traces were not recorded" in n.lower() for n in pkg.notes)

