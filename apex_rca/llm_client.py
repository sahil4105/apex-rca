"""Modular Groq client and diagnosis generation for APEX-RCA."""

from __future__ import annotations

import json
import os
import time
from typing import Any

from dotenv import load_dotenv

from apex_rca.llm_evidence import EvidencePackage
from apex_rca.llm_report import IncidentReport, report_json_schema

load_dotenv()

DEFAULT_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-20b")
DEFAULT_TEMPERATURE = 0.0
DEFAULT_MAX_TOKENS = 1200


def _failure_category(error: BaseException | str | None) -> str:
    message = str(error or "").lower()
    if not message:
        return "unexpected_exception"
    if any(token in message for token in ["429", "rate limit", "quota", "too many requests"]):
        return "rate_limit"
    if any(token in message for token in ["timeout", "timed out", "deadline"]):
        return "timeout"
    if any(token in message for token in ["api key", "unauthorized", "authentication", "forbidden"]):
        return "missing_api_key"
    if any(token in message for token in ["json", "decode", "parse", "malformed"]):
        return "malformed_response"
    return "unexpected_exception"


def get_groq_client() -> Any | None:
    """Return an initialized Groq client if the SDK and API key are available."""
    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    if not api_key:
        return None
    try:
        from groq import Groq

        return Groq(api_key=api_key)
    except Exception:
        return None


def build_system_prompt() -> str:
    """System prompt instructing the model on schema compliance and citation discipline."""
    schema_str = json.dumps(report_json_schema(), indent=2)
    return (
        "You are an expert site reliability and root-cause analysis engineer for microservices.\n"
        "Your task is to analyze telemetry evidence from an incident and determine the most likely root-cause service.\n\n"
        "RULES FOR DIAGNOSIS:\n"
        "1. GROUNDING: Base your diagnosis solely on the provided incident evidence and candidate services. "
        "Do NOT invent unobserved events, nonexistent metrics, or unlisted services.\n"
        "2. CANDIDATE CONSTRAINT: Your suspected_root_cause MUST be selected from the provided Candidate Services list.\n"
        "3. CITATIONS: In supporting_claims, you MUST cite the exact evidence IDs (e.g. ['EVID-METRIC-01', 'EVID-TOPO-02']) "
        "that justify each specific claim. If working with raw logs, leave evidence_ids empty and quote key log events in claim_text.\n"
        "4. ALTERNATIVES: Explicitly discuss why runner-up candidates are less likely than your primary suspect.\n"
        "5. OBJECTIVITY: Explicitly state contradictory signals or missing telemetry under contradictory_evidence and uncertainty_and_limitations.\n"
        "6. FORMAT: You MUST return a single valid JSON object strictly matching this JSON schema:\n"
        f"{schema_str}\n"
        "Output ONLY the JSON object. Do not include markdown code block formatting (no ```json)."
    )


def build_user_prompt(package: EvidencePackage) -> str:
    """Format the evidence package into the user prompt."""
    prompt_text = package.format_for_prompt()
    instructions = (
        "\n\nPlease analyze the above incident evidence and output the structured JSON incident report "
        "identifying the suspected root-cause service and citing supporting evidence IDs."
    )
    return prompt_text + instructions


def generate_incident_diagnosis(
    package: EvidencePackage,
    *,
    client: Any | None = None,
    model: str | None = None,
    temperature: float = DEFAULT_TEMPERATURE,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    deterministic_fallback_explanations: list[dict[str, Any]] | None = None,
) -> tuple[IncidentReport, dict[str, Any]]:
    """Generate a structured incident diagnosis report via Groq.

    If client is None, API key is missing, or an API error occurs,
    gracefully returns a fallback report from deterministic scoring.
    """
    selected_model = model or os.environ.get("GROQ_MODEL", DEFAULT_MODEL)
    metadata: dict[str, Any] = {
        "model": selected_model,
        "success": False,
        "fallback_used": False,
        "llm_call_successful": False,
        "latency_s": 0.0,
        "prompt_tokens": None,
        "completion_tokens": None,
        "error": None,
        "error_detail": None,
        "failure_category": None,
    }

    if client is None:
        client = get_groq_client()

    if client is None:
        metadata["fallback_used"] = True
        metadata["llm_call_successful"] = False
        metadata["failure_category"] = "missing_api_key"
        metadata["error"] = "Groq client unavailable (GROQ_API_KEY unset or groq SDK missing)"
        metadata["error_detail"] = metadata["error"]
        fallback_rep = IncidentReport.fallback_from_deterministic(
            ranked_candidates=[
                (svc, package.candidate_scores.get(svc, 0.0))
                for svc in package.candidate_services
            ],
            explanations=deterministic_fallback_explanations or [],
            note="Groq client unavailable; returned deterministic baseline diagnosis.",
        )
        return fallback_rep, metadata

    system_prompt = build_system_prompt()
    user_prompt = build_user_prompt(package)

    started = time.perf_counter()
    try:
        response = client.chat.completions.create(
            model=selected_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
        )
        latency = time.perf_counter() - started
        metadata["latency_s"] = latency

        content = response.choices[0].message.content or "{}"
        if hasattr(response, "usage") and response.usage:
            metadata["prompt_tokens"] = getattr(response.usage, "prompt_tokens", None)
            metadata["completion_tokens"] = getattr(response.usage, "completion_tokens", None)

        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            cleaned = content.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.strip("`")
                if cleaned.lower().startswith("json"):
                    cleaned = cleaned[4:].strip()
            try:
                data = json.loads(cleaned)
            except json.JSONDecodeError:
                metadata["success"] = False
                metadata["fallback_used"] = True
                metadata["llm_call_successful"] = False
                metadata["failure_category"] = "malformed_response"
                metadata["error"] = "API error: JSONDecodeError: model response was not valid JSON"
                metadata["error_detail"] = metadata["error"]
                fallback_rep = IncidentReport.fallback_from_deterministic(
                    ranked_candidates=[
                        (svc, package.candidate_scores.get(svc, 0.0))
                        for svc in package.candidate_services
                    ],
                    explanations=deterministic_fallback_explanations or [],
                    note="LLM response was not valid JSON; returned deterministic baseline.",
                )
                fallback_rep.generation_latency_s = time.perf_counter() - started
                return fallback_rep, metadata

        data["model_name"] = selected_model
        data["generation_latency_s"] = latency
        data["prompt_tokens"] = metadata["prompt_tokens"]
        data["completion_tokens"] = metadata["completion_tokens"]

        report = IncidentReport.from_dict(data, raw_response=content)
        metadata["success"] = True
        metadata["llm_call_successful"] = True
        metadata["failure_category"] = None
        metadata["error"] = None
        metadata["error_detail"] = None
        return report, metadata

    except Exception as exc:
        latency = time.perf_counter() - started
        metadata["latency_s"] = latency
        metadata["fallback_used"] = True
        metadata["llm_call_successful"] = False
        metadata["failure_category"] = _failure_category(exc)
        metadata["error"] = f"API error: {type(exc).__name__}: {str(exc)}"
        metadata["error_detail"] = metadata["error"]

        fallback_rep = IncidentReport.fallback_from_deterministic(
            ranked_candidates=[
                (svc, package.candidate_scores.get(svc, 0.0))
                for svc in package.candidate_services
            ],
            explanations=deterministic_fallback_explanations or [],
            note=f"LLM API call failed ({metadata['error']}); returned deterministic baseline.",
        )
        fallback_rep.generation_latency_s = latency
        return fallback_rep, metadata

