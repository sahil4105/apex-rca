import pytest

from apex_rca.llm_evidence import EvidenceItem, EvidencePackage
from apex_rca.llm_report import AlternativeCandidate, IncidentReport, SupportingClaim
from apex_rca.llm_validation import validate_report


def test_validation_detects_valid_citations_and_candidates():
    package = EvidencePackage(
        case_id="case_1",
        system="sock_shop",
        method_variant="topology_anomaly",
        candidate_services=["catalogue", "orders", "payment"],
        candidate_ranks={"catalogue": 1, "orders": 2, "payment": 3},
        candidate_scores={"catalogue": 0.8, "orders": 0.5, "payment": 0.2},
        items=[
            EvidenceItem(
                id="EVID-METRIC-01",
                service="catalogue",
                modality="metric",
                description="High CPU",
            ),
            EvidenceItem(
                id="EVID-TOPO-01",
                service="catalogue",
                modality="topology",
                description="Root node",
            ),
        ],
    )

    report = IncidentReport(
        suspected_root_cause="catalogue",
        confidence="high",
        possible_fault_type="cpu_exhaustion",
        reasoning_summary="catalogue shows highest CPU and topology centrality.",
        supporting_claims=[
            SupportingClaim(
                claim_text="CPU spike observed",
                evidence_ids=["EVID-METRIC-01"],
            ),
            SupportingClaim(
                claim_text="Central caller service",
                evidence_ids=["EVID-TOPO-01"],
            ),
        ],
        alternative_candidates=[
            AlternativeCandidate(service="orders", rationale="Less anomaly"),
        ],
        contradictory_evidence=[],
        uncertainty_and_limitations=["No trace spans recorded."],
    )

    audit = validate_report(report, package)

    assert audit.is_valid_structure is True
    assert audit.is_valid_candidate is True
    assert audit.total_claims == 2
    assert audit.total_citations == 2
    assert audit.citation_validity_ratio == 1.0
    assert audit.unsupported_claim_count == 0
    assert len(audit.invalid_citations) == 0
    assert audit.has_alternative_candidates is True
    assert audit.has_contradictions_or_limitations is True


def test_validation_flags_hallucinated_citations_and_invalid_candidate():
    package = EvidencePackage(
        case_id="case_1",
        system="sock_shop",
        method_variant="topology_anomaly",
        candidate_services=["catalogue", "orders"],
        candidate_ranks={"catalogue": 1, "orders": 2},
        candidate_scores={"catalogue": 0.8, "orders": 0.5},
        items=[
            EvidenceItem(
                id="EVID-METRIC-01",
                service="catalogue",
                modality="metric",
                description="High CPU",
            ),
        ],
    )

    report = IncidentReport(
        suspected_root_cause="unrelated_service",  # NOT in candidates!
        confidence="high",
        possible_fault_type="network_delay",
        reasoning_summary="Unrelated service failed.",
        supporting_claims=[
            SupportingClaim(
                claim_text="Fabricated claim citing non-existent evidence",
                evidence_ids=["EVID-METRIC-99", "EVID-FAKE-01"],  # Hallucinated IDs!
            ),
            SupportingClaim(
                claim_text="Uncited claim",
                evidence_ids=[],  # Unsupported
            ),
        ],
        alternative_candidates=[],
        contradictory_evidence=[],
        uncertainty_and_limitations=[],
    )

    audit = validate_report(report, package)

    assert audit.is_valid_structure is True
    assert audit.is_valid_candidate is False  # Flagged!
    assert "unrelated_service" in audit.warnings[0]
    assert audit.total_citations == 2
    assert len(audit.invalid_citations) == 2
    assert audit.citation_validity_ratio == 0.0
    assert audit.unsupported_claim_count == 2
    assert any("hallucinated" in w.lower() for w in audit.warnings)

