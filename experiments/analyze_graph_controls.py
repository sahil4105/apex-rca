"""Additive inferential analysis for existing graph-control paired outputs.

This script reads the original graph-control artifacts and writes a new JSON
report. It never rewrites the original long, paired, or summary CSVs.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apex_rca.evaluation import (
    EVALUATION_METRICS,
    apply_holm_correction,
    paired_metric_comparison,
)


def _control_report(
    paired_path: Path,
    *,
    condition_b: str,
    seed: int,
) -> dict[str, object]:
    frame = pd.read_csv(paired_path)
    comparisons = []
    for metric in EVALUATION_METRICS:
        comparisons.append(
            paired_metric_comparison(
                frame[f"{metric}_real_graph"],
                frame[f"{metric}_{condition_b}"],
                metric=metric,
                seed=seed,
            )
        )
    return {
        "source": str(paired_path),
        "n_eligible_cases": int(len(frame)),
        "condition_a": "real_graph",
        "condition_b": condition_b,
        "comparisons_holm": apply_holm_correction(comparisons),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analyze existing graph-control paired CSVs."
    )
    parser.add_argument("--results-dir", default="results")
    parser.add_argument(
        "--output",
        default="results/graph_control_inference_v1.json",
    )
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    results = Path(args.results_dir)
    reports: dict[str, object] = {}

    degree_path = results / "graph_control_paired_cases.csv"
    if degree_path.exists():
        reports["degree_preserving"] = _control_report(
            degree_path,
            condition_b="shuffled_graph",
            seed=args.seed,
        )

    random_path = results / "graph_control_random_paired_cases.csv"
    if random_path.exists():
        reports["unconstrained_random"] = _control_report(
            random_path,
            condition_b="random_graph",
            seed=args.seed,
        )

    if not reports:
        raise FileNotFoundError("No graph-control paired CSVs were found.")

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            {
                "seed": args.seed,
                "reports": reports,
                "note": (
                    "Randomized repetitions are averaged within case before "
                    "paired inference; they are not treated as independent cases."
                ),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Wrote {output}")


if __name__ == "__main__":
    main()
