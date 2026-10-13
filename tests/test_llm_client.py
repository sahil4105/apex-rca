import os
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from apex_rca.llm_client import generate_incident_diagnosis
from experiments.run_llm_experiments import prepare_output_dir
from apex_rca.llm_evidence import EvidenceItem, EvidencePackage
from apex_rca.llm_report import IncidentReport


def sample_package() -> EvidencePackage:
    return EvidencePackage(
        case_id="case_mock_01",
        system="online_boutique",
        method_variant="topology_anomaly",
        candidate_services=["frontend", "recommendation"],
        candidate_ranks={"frontend": 1, "recommendation": 2},
        candidate_scores={"frontend": 0.88, "recommendation": 0.45},
        items=[
            EvidenceItem(
                id="EVID-METRIC-01",
                service="frontend",
                modality="metric",
                description="CPU load spike 95%",
            ),
            EvidenceItem(
                id="EVID-TOPO-01",
                service="frontend",
                modality="topology",
                description="Root caller node",
            ),
        ],
    )


def test_client_fallback_when_client_is_none():
    package = sample_package()
    # Explicitly pass client=None and unset key scenario
    report, meta = generate_incident_diagnosis(
        package,
        client=None,
        deterministic_fallback_explanations=[
            {"service": "frontend", "reasons": ["Heuristic top metric anomaly"]}
        ],
    )

    # If the environment happens to have a live key, it might use it, but if client is mocked to None or error:
    # Let's test with a mock that fails or verifies fallback behavior
    assert isinstance(report, IncidentReport)
    assert report.suspected_root_cause in package.candidate_services


def test_mocked_groq_client_success():
    package = sample_package()

    mock_client = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = """
    {
      "suspected_root_cause": "frontend",
      "confidence": "high",
      "possible_fault_type": "cpu_exhaustion",
      "reasoning_summary": "Frontend experienced massive CPU spike and is root in topology.",
      "supporting_claims": [
        {"claim_text": "Severe CPU increase", "evidence_ids": ["EVID-METRIC-01"]},
        {"claim_text": "Root caller in graph", "evidence_ids": ["EVID-TOPO-01"]}
      ],
      "alternative_candidates": [
        {"service": "recommendation", "rationale": "Much lower anomaly score"}
      ],
      "contradictory_evidence": [],
      "uncertainty_and_limitations": ["Traces were not recorded"]
    }
    """
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_response.usage.prompt_tokens = 250
    mock_response.usage.completion_tokens = 120
    mock_client.chat.completions.create.return_value = mock_response

    report, meta = generate_incident_diagnosis(package, client=mock_client)

    assert meta["success"] is True
    assert meta["fallback_used"] is False
    assert report.suspected_root_cause == "frontend"
    assert report.confidence == "high"
    assert report.possible_fault_type == "cpu_exhaustion"
    assert len(report.supporting_claims) == 2
    assert report.supporting_claims[0].evidence_ids == ["EVID-METRIC-01"]
    assert meta["prompt_tokens"] == 250
    assert meta["completion_tokens"] == 120


def test_mocked_groq_client_handles_api_exception_cleanly():
    package = sample_package()

    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = RuntimeError("Groq 429 Rate Limit Exceeded")

    report, meta = generate_incident_diagnosis(
        package,
        client=mock_client,
        deterministic_fallback_explanations=[{"service": "frontend", "reasons": ["Fallback rule"]}],
    )

    assert meta["success"] is False
    assert meta["fallback_used"] is True
    assert meta["failure_category"] == "rate_limit"
    assert "Rate Limit" in meta["error"]
    assert report.suspected_root_cause == "frontend"
    assert report.model_name == "deterministic_fallback"
    assert any("LLM API call failed" in item for item in report.uncertainty_and_limitations)


def test_missing_api_key_uses_deterministic_fallback(monkeypatch):
    package = sample_package()
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    report, meta = generate_incident_diagnosis(
        package,
        client=None,
        deterministic_fallback_explanations=[{"service": "frontend", "reasons": ["Fallback rule"]}],
    )

    assert meta["fallback_used"] is True
    assert meta["failure_category"] == "missing_api_key"
    assert "GROQ_API_KEY" in meta["error"]
    assert report.suspected_root_cause == "frontend"


def test_malformed_json_response_uses_fallback():
    package = sample_package()
    mock_client = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = "```json\n{not valid json}\n```"
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_response.usage.prompt_tokens = 10
    mock_response.usage.completion_tokens = 5
    mock_client.chat.completions.create.return_value = mock_response

    report, meta = generate_incident_diagnosis(
        package,
        client=mock_client,
        deterministic_fallback_explanations=[{"service": "frontend", "reasons": ["fallback"]}],
    )

    assert meta["fallback_used"] is True
    assert meta["failure_category"] == "malformed_response"
    assert report.suspected_root_cause == "frontend"


def test_prepare_output_dir_refuses_existing_nonempty_directory(tmp_path):
    out_dir = tmp_path / "existing-results"
    out_dir.mkdir()
    (out_dir / "notes.txt").write_text("keep me", encoding="utf-8")

    with pytest.raises(FileExistsError):
        prepare_output_dir(out_dir)

    prepared = prepare_output_dir(out_dir, overwrite=True)
    assert prepared == out_dir

