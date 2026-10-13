from pathlib import Path
import sys
import json
import time

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DATA_DIR = ROOT / "data" / "openrca" / "processed" / "Bank"
RESULTS_DIR = ROOT / "results"
from apex_rca.config import CANONICAL_REFERENCE_SECONDS

TAG = "bank_canonical_v1"
MIN_SAMPLES = 10
WINDOW_SECONDS = CANONICAL_REFERENCE_SECONDS


def evaluate_incident(index):
    from apex_rca.bank_adapter import load_bank_incident
    from apex_rca.canonical_scoring import score_canonical_incident

    incident, truth = load_bank_incident(
        DATA_DIR, index,
        reference_seconds=WINDOW_SECONDS,
        observed_seconds=WINDOW_SECONDS,
    )
    scores, _ = score_canonical_incident(
        incident.metrics,
        incident.incident_time,
        reference_seconds=WINDOW_SECONDS,
        observed_seconds=WINDOW_SECONDS,
        min_samples=MIN_SAMPLES,
    )

    candidates = sorted(incident.metrics["service"].unique())
    truth_component = truth["component"]
    truth_scoreable = truth_component in scores

    row = {
        "incident_index": index,
        "incident_id": incident.incident_id,
        "truth_component": truth_component,
        "fault_label": truth["reason"],
        "components_in_data": len(candidates),
        "scored_components": len(scores),
        "truth_scoreable": truth_scoreable,
        "strict_hit1": None,
        "tie_aware_hit1": None,
        "average_rank": None,
        "tie_aware_reciprocal_rank": None,
        "top_components": "",
        "top_score": None,
        "top_tie_count": 0,
        "status": "unscorable",
    }

    if not scores:
        row["status"] = "no_components_scored"
        return row

    top_score = max(scores.values())
    top_components = sorted(
        service for service, score in scores.items()
        if np.isclose(score, top_score, rtol=1e-12, atol=1e-12)
    )
    row["top_components"] = ";".join(top_components)
    row["top_score"] = float(top_score)
    row["top_tie_count"] = len(top_components)

    if not truth_scoreable:
        row["status"] = "truth_component_unscorable"
        return row

    truth_score = scores[truth_component]
    higher = sum(
        score > truth_score and not np.isclose(
            score, truth_score, rtol=1e-12, atol=1e-12
        )
        for score in scores.values()
    )
    tied = sum(
        np.isclose(score, truth_score, rtol=1e-12, atol=1e-12)
        for score in scores.values()
    )
    average_rank = higher + (tied + 1) / 2

    row["strict_hit1"] = int(
        len(top_components) == 1 and top_components[0] == truth_component
    )
    row["tie_aware_hit1"] = int(truth_component in top_components)
    row["average_rank"] = float(average_rank)
    row["tie_aware_reciprocal_rank"] = float(1 / average_rank)
    row["status"] = "evaluated"
    return row


def main():
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    records = pd.read_csv(DATA_DIR / "record.csv")
    rows = []
    started = time.time()

    for index in range(len(records)):
        try:
            row = evaluate_incident(index)
        except Exception as exc:
            row = {
                "incident_index": index,
                "incident_id": f"bank-{index:03d}",
                "truth_component": str(records.iloc[index]["component"]).strip(),
                "fault_label": str(records.iloc[index]["reason"]),
                "components_in_data": None,
                "scored_components": 0,
                "truth_scoreable": False,
                "strict_hit1": None,
                "tie_aware_hit1": None,
                "average_rank": None,
                "tie_aware_reciprocal_rank": None,
                "top_components": "",
                "top_score": None,
                "top_tie_count": 0,
                "status": f"error: {type(exc).__name__}: {exc}",
            }

        rows.append(row)
        if (index + 1) % 10 == 0 or index + 1 == len(records):
            print(f"Processed {index + 1}/{len(records)} incidents")

    frame = pd.DataFrame(rows)
    per_case_path = RESULTS_DIR / f"{TAG}_per_incident.csv"
    summary_path = RESULTS_DIR / f"{TAG}_summary.json"
    frame.to_csv(per_case_path, index=False)

    evaluated = frame[frame["status"] == "evaluated"]
    summary = {
        "dataset": "OpenRCA-Bank",
        "tag": TAG,
        "incidents_total": int(len(frame)),
        "evaluated": int(len(evaluated)),
        "unscorable_or_error": int(len(frame) - len(evaluated)),
        "truth_component_scoreable": int(frame["truth_scoreable"].sum()),
        "mean_scored_components": (
            float(frame["scored_components"].mean()) if len(frame) else None
        ),
        "strict_hit1": (
            float(evaluated["strict_hit1"].mean()) if len(evaluated) else None
        ),
        "tie_aware_hit1": (
            float(evaluated["tie_aware_hit1"].mean()) if len(evaluated) else None
        ),
        "tie_aware_mrr": (
            float(evaluated["tie_aware_reciprocal_rank"].mean())
            if len(evaluated) else None
        ),
        "status_counts": {
            str(key): int(value)
            for key, value in frame["status"].value_counts().items()
        },
        "configuration": {
            "reference_seconds": WINDOW_SECONDS,
            "observed_seconds": WINDOW_SECONDS,
            "min_samples_per_metric_per_window": MIN_SAMPLES,
            "tie_policy": "average rank; Hit@1 reported both strictly and tie-aware",
            "scoring": "median shift / robust MAD scale; top 3 metric effects averaged; effect cap 20",
        },
        "elapsed_seconds": round(time.time() - started, 2),
        "per_incident_csv": str(per_case_path.relative_to(ROOT)),
    }
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print("\nSUMMARY")
    print(json.dumps(summary, indent=2))
    print("\nPer-incident results:", per_case_path)
    print("Summary:", summary_path)


if __name__ == "__main__":
    main()


