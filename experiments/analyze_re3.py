"""Investigate why the anomaly-only baseline is weaker on RE3.

This script does not train on labels. It only reports score diagnostics:
whether the labelled root cause has a weak metric-change signal relative
to other services, broken down by system and fault type.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apex_rca.config import ExperimentConfig, default_rcaeval_dir, default_results_dir
from apex_rca.data_loader import load_index
from apex_rca.pipeline import run_case


def main() -> None:
    data_dir = default_rcaeval_dir()
    results_dir = default_results_dir()
    results_dir.mkdir(parents=True, exist_ok=True)
    config = ExperimentConfig(name="re3_audit")
    index = load_index(data_dir)
    re3 = index[index["suite"].astype(str) == "RE3"].sort_values("case")

    rows = []
    for _, row in re3.iterrows():
        result = run_case(data_dir, row, config, "anomaly_only")
        if result.skip_reason:
            rows.append(
                {
                    "case": result.case,
                    "system": result.system,
                    "fault": result.fault,
                    "root_cause": result.root_cause,
                    "skipped": result.skip_reason,
                }
            )
            continue
        scores = result.extras.get("metric_scores", {})
        truth = result.root_cause
        truth_score = scores.get(truth)
        others = [v for k, v in scores.items() if k != truth]
        rows.append(
            {
                "case": result.case,
                "system": result.system,
                "fault": result.fault,
                "root_cause": truth,
                "skipped": "",
                "n_candidates": len(scores),
                "truth_score": truth_score,
                "truth_rank": result.rank,
                "max_other": max(others) if others else None,
                "median_other": float(pd.Series(others).median()) if others else None,
                "hit1": result.hit1,
                "top3": result.to_row()["top3"],
            }
        )

    frame = pd.DataFrame(rows)
    out = results_dir / "re3_anomaly_audit.csv"
    frame.to_csv(out, index=False)
    valid = frame[frame["skipped"].fillna("") == ""]
    print("RE3 anomaly-signal audit")
    print(f"Cases: {len(frame)}  evaluated: {len(valid)}")
    if valid.empty:
        return
    valid = valid.copy()
    valid["truth_is_max"] = valid["truth_score"] >= valid["max_other"]
    print("\nShare of cases where labelled RC has the highest metric score:")
    print(valid.groupby("system")["truth_is_max"].mean().round(4).to_string())
    print("\nMean truth rank by system:")
    print(valid.groupby("system")["truth_rank"].mean().round(3).to_string())
    print("\nHit@1 by system / fault:")
    print(valid.groupby(["system", "fault"])["hit1"].agg(["mean", "count"]).round(4).to_string())
    weak = valid[valid["truth_score"] < valid["median_other"]]
    print(f"\nCases where RC score < median of others: {len(weak)}/{len(valid)}")
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
