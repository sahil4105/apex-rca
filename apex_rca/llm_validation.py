"""Evidence validation and hallucination auditing for LLM-generated incident reports."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from apex_rca.llm_evidence import EvidencePackage
from apex_rca.llm_report import IncidentReport


@dataclass
class ValidationResult:
    """Quantitative validation audit of an LLM incident report."""

    is_valid_structure: bool
    is_valid_candidate: bool
    total_claims: int
    total_citations: int
    valid_citations: list[str] = field(default_factory=list)
    invalid_citations: list[str] = field(default_factory=list)
    citation_validity_ratio: float = 0.0
    unsupported_claim_count: int = 0
    unsupported_claim_ratio: float = 0.0
    has_alternative_candidates: bool = False
    has_contradictions_or_limitations: bool = False
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_valid_structure": self.is_valid_structure,
            "is_valid_candidate": self.is_valid_candidate,
            "total_claims": self.total_claims,
            "total_citations": self.total_citations,
            "valid_citations": list(self.valid_citations),
            "invalid_citations": list(self.invalid_citations),
            "citation_validity_ratio": self.citation_validity_ratio,
            "unsupported_claim_count": self.unsupported_claim_count,
            "unsupported_claim_ratio": self.unsupported_claim_ratio,
            "has_alternative_candidates": self.has_alternative_candidates,
            "has_contradictions_or_limitations": self.has_contradictions_or_limitations,
            "warnings": list(self.warnings),
        }


def validate_report(report: IncidentReport, package: EvidencePackage) -> ValidationResult:
    """Audit the incident report against provided evidence.

    NOTE: High citation validity means cited IDs exist in the prompt package;
    it does NOT imply the report is entirely hallucination-free. Claims and citations
    are audited quantitatively.
    """
    warnings: list[str] = []

    # 1. Structural validity
    is_valid_structure = bool(
        report.suspected_root_cause
        and report.confidence in {"high", "medium", "low"}
        and report.reasoning_summary
    )
    if not is_valid_structure:
        warnings.append("Report missing required fields or has invalid confidence enum.")

    # 2. Candidate boundary validity
    candidates_set = set(package.candidate_services)
    is_valid_candidate = report.suspected_root_cause in candidates_set
    if not is_valid_candidate:
        warnings.append(
            f"Suspected root cause '{report.suspected_root_cause}' was NOT in provided "
            f"candidate services: {sorted(candidates_set)}."
        )

    # 3. Citation and grounding audit
    valid_ids_set = package.valid_evidence_ids
    total_claims = len(report.supporting_claims)
    all_cited: list[str] = []
    valid_citations: list[str] = []
    invalid_citations: list[str] = []
    unsupported_claim_count = 0

    for claim in report.supporting_claims:
        claim_cited = [str(eid).strip() for eid in claim.evidence_ids if str(eid).strip()]
        all_cited.extend(claim_cited)

        claim_valid_cites = [cid for cid in claim_cited if cid in valid_ids_set]
        claim_invalid_cites = [cid for cid in claim_cited if cid not in valid_ids_set]

        valid_citations.extend(claim_valid_cites)
        invalid_citations.extend(claim_invalid_cites)

        # In structured modes (anomaly_only, topology_anomaly), claims should have at least 1 valid citation
        if package.method_variant != "raw_logs":
            if not claim_valid_cites:
                unsupported_claim_count += 1

    total_citations = len(all_cited)
    if total_citations > 0:
        citation_validity_ratio = len(valid_citations) / total_citations
    else:
        # In raw_logs mode, lack of discrete evidence IDs is expected
        citation_validity_ratio = 1.0 if package.method_variant == "raw_logs" else 0.0

    unsupported_claim_ratio = (
        unsupported_claim_count / total_claims if total_claims > 0 else 0.0
    )

    if invalid_citations:
        warnings.append(
            f"Detected {len(invalid_citations)} hallucinated or invalid evidence IDs: "
            f"{invalid_citations[:5]}"
        )
    if package.method_variant != "raw_logs" and unsupported_claim_count > 0:
        warnings.append(
            f"{unsupported_claim_count} of {total_claims} claims lack citations to valid evidence items."
        )

    # 4. Alternative candidates and limitations audit
    has_alts = len(report.alternative_candidates) > 0
    if not has_alts:
        warnings.append("Report did not evaluate alternative runner-up candidate services.")

    has_contradictions_or_limits = bool(
        report.contradictory_evidence or report.uncertainty_and_limitations
    )
    if not has_contradictions_or_limits:
        warnings.append("Report did not acknowledge any contradictory evidence or limitations.")

    return ValidationResult(
        is_valid_structure=is_valid_structure,
        is_valid_candidate=is_valid_candidate,
        total_claims=total_claims,
        total_citations=total_citations,
        valid_citations=valid_citations,
        invalid_citations=invalid_citations,
        citation_validity_ratio=round(citation_validity_ratio, 4),
        unsupported_claim_count=unsupported_claim_count,
        unsupported_claim_ratio=round(unsupported_claim_ratio, 4),
        has_alternative_candidates=has_alts,
        has_contradictions_or_limitations=has_contradictions_or_limits,
        warnings=warnings,
    )

