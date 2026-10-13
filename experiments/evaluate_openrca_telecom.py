from __future__ import annotations

import json
import argparse
import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apex_rca.canonical_scoring import score_canonical_incident
from apex_rca.config import CANONICAL_OBSERVED_SECONDS, CANONICAL_REFERENCE_SECONDS
from apex_rca.telecom_adapter import load_telecom_incident


DATA_DIR = ROOT / "data" / "openrca" / "processed" / "Telecom"
RESULTS_DIR = ROOT / "results"
parser = argparse.ArgumentParser()
parser.add_argument("--tag", default="telecom_canonical_v1")
parser.add_argument("--min-samples", type=int, default=10)
TAG = parser.parse_args().tag
MIN_SAMPLES = parser.parse_args().min_samples


def evaluate_incident(index: int) -> dict:
    started = time.perf_counter()
    base = {
        "incident_index": index,
        "incident_id": f"telecom-{index:03d}",
        "status": "error",
        "truth_component": None,
        "truth_reason": None,
        "truth_level": None,
        "scored_components": 0,
        "truth_scoreable": False,
        "truth_rank": None,
        "strict_hit1": 0,
        "tie_aware_hit1": 0,
        "reciprocal_rank": 0.0,
        "top_component": None,
        "top_score": None,
        "top_components": None,
        "error": None,
    }

    try:
        incident, truth = load_telecom_incident(
            DATA_DIR,
            index,
            reference_seconds=CANONICAL_REFERENCE_SECONDS,
            observed_seconds=CANONICAL_OBSERVED_SECONDS,
        )
        base.update({
            "truth_component": truth["component"],
            "truth_reason": truth["reason"],
            "truth_level": truth["level"],
            "metric_rows": len(incident.metrics),
            "candidate_components": incident.metrics["service"].nunique(),
            "metric_categories": ",".join(incident.metadata["metric_categories"]),
        })

        scores, details = score_canonical_incident(
            incident.metrics,
            incident.incident_time,
            reference_seconds=CANONICAL_REFERENCE_SECONDS,
            observed_seconds=CANONICAL_OBSERVED_SECONDS,
            min_samples=MIN_SAMPLES,
        )
        base["scored_components"] = len(scores)

        if not scores:
            base["status"] = "no_components_scored"
            return base

        ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
        base["top_component"] = ranked[0][0]
        base["top_score"] = float(ranked[0][1])
        base["top_components"] = ";".join(
            component for component, score in ranked
            if score == ranked[0][1]
        )

        target = truth["component"]
        if target not in scores:
            base["status"] = "truth_not_scoreable"
            return base

        target_score = scores[target]
        greater = sum(score > target_score for score in scores.values())
        equal = sum(score == target_score for score in scores.values())
        average_rank = greater + (equal + 1) / 2
        max_score = max(scores.values())
        top_tie_count = sum(score == max_score for score in scores.values())

        base.update({
            "status": "evaluated",
            "truth_scoreable": True,
            "truth_rank": float(average_rank),
            "strict_hit1": int(target_score == max_score and top_tie_count == 1),
            "tie_aware_hit1": int(target_score == max_score),
            "reciprocal_rank": float(1.0 / average_rank),
        })
        return base

    except Exception as exc:
        base["error"] = f"{type(exc).__name__}: {exc}"
        return base

    finally:
        base["elapsed_seconds"] = round(time.perf_counter() - started, 3)


def main() -> int:
    if not (DATA_DIR / "record.csv").is_file():
        print(f"Missing Telecom record file: {DATA_DIR / 'record.csv'}")
        return 1

    records = pd.read_csv(DATA_DIR / "record.csv")
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    per_incident_path = RESULTS_DIR / f"{TAG}_per_incident.csv"
    summary_path = RESULTS_DIR / f"{TAG}_summary.json"

    results = []
    total = len(records)
    print(f"Dataset: OpenRCA-Telecom")
    print(f"Incidents: {total}")
    print(f"Reference/observed windows: {CANONICAL_REFERENCE_SECONDS}s each")
    print(f"Minimum samples per metric per window: {MIN_SAMPLES}")
    print("Ground-truth labels are used only after scoring for evaluation.")
    print()

    for index in range(total):
        row = evaluate_incident(index)
        results.append(row)
        print(
            f"[{index + 1:02d}/{total}] {row['incident_id']}: "
            f"{row['status']}; truth={row['truth_component']}; "
            f"scored={row['scored_components']}; "
            f"rank={row['truth_rank']}; "
            f"time={row.get('elapsed_seconds', 0):.1f}s"
        )
        if row["error"]:
            print(f"    {row['error']}")

        # Save progress after every incident, so an interruption loses little work.
        pd.DataFrame(results).to_csv(per_incident_path, index=False)

    frame = pd.DataFrame(results)
    evaluated = frame[frame["status"] == "evaluated"]
    summary = {
        "dataset": "OpenRCA-Telecom",
        "tag": TAG,
        "incidents_total": int(total),
        "incidents_evaluated": int(len(evaluated)),
        "incidents_unscorable_or_error": int(total - len(evaluated)),
        "status_counts": {
            str(key): int(value)
            for key, value in frame["status"].value_counts(dropna=False).items()
        },
        "truth_component_scoreable": int(frame["truth_scoreable"].sum()),
        "mean_scored_components": (
            float(frame.loc[frame["status"] == "evaluated", "scored_components"].mean())
            if len(evaluated) else None
        ),
        "strict_hit1": (
            float(evaluated["strict_hit1"].mean()) if len(evaluated) else None
        ),
        "tie_aware_hit1": (
            float(evaluated["tie_aware_hit1"].mean()) if len(evaluated) else None
        ),
        "tie_aware_mrr": (
            float(evaluated["reciprocal_rank"].mean()) if len(evaluated) else None
        ),
        "configuration": {
            "reference_seconds": CANONICAL_REFERENCE_SECONDS,
            "observed_seconds": CANONICAL_OBSERVED_SECONDS,
            "min_samples_per_window": MIN_SAMPLES,
            "scoring": "canonical robust median-shift effect with MAD/std fallback and capped effect",
            "application_metrics_included": False,
            "candidate_scope": "all components with scoreable infrastructure metrics in the incident window",
            "tie_policy": "average rank for reciprocal rank; tie-aware Hit@1 counts all components tied for highest score",
        },
        "elapsed_seconds": round(float(frame["elapsed_seconds"].sum()), 3),
        "per_incident_csv": str(per_incident_path.relative_to(ROOT)),
    }

    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print("\n=== Summary ===")
    print(json.dumps(summary, indent=2))
    print(f"\nSaved: {per_incident_path}")
    print(f"Saved: {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
