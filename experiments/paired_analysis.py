
"""Paired statistical analysis of existing RCAEval result CSVs.

Reads existing result files only. Does not rerun experiments or overwrite
existing results. Writes a separate Markdown report.
"""

from __future__ import annotations

import argparse

import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from apex_rca.evaluation import compare_method_dataframes


METHOD_FILES = {
    "anomaly_only": "anomaly_only_full2.csv",
    "metrics_graph": "metrics_graph_full2.csv",
    "metrics_logs_traces": "metrics_logs_traces_full2.csv",
    "full": "full_full2.csv",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Paired statistical analysis of existing RCAEval results."
    )
    parser.add_argument("--results-dir", default="results")
    parser.add_argument(
        "--output",
        default="results/paired_analysis_full2.md",
    )
    parser.add_argument("--bootstrap", type=int, default=10000)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def fmt(value: object) -> str:
    if value is None or pd.isna(value):
        return "—"
    if isinstance(value, (float, int)):
        return f"{value:.6f}"
    return str(value)


def main() -> None:
    args = parse_args()
    results_dir = Path(args.results_dir)

    frames: dict[str, pd.DataFrame] = {}
    for method, filename in METHOD_FILES.items():
        path = results_dir / filename
        if not path.exists():
            raise FileNotFoundError(f"Missing result file: {path}")

        frame = pd.read_csv(path)
        required = {"case", "hit1", "hit3", "hit5", "mrr"}
        missing = required - set(frame.columns)
        if missing:
            raise ValueError(f"{filename} is missing columns: {sorted(missing)}")
        if frame["case"].duplicated().any():
            raise ValueError(f"{filename} contains duplicate case IDs.")
        frames[method] = frame

    comparisons: list[dict] = []

    for baseline_method, method in (
            ("anomaly_only", "metrics_graph"),
            ("anomaly_only", "metrics_logs_traces"),
            ("anomaly_only", "full"),
            ("metrics_graph", "full"),
    ):
        result = compare_method_dataframes(
            frames[baseline_method],
            frames[method],
            label_a=baseline_method,
            label_b=method,
            seed=args.seed,
            n_boot=args.bootstrap,
        )
        for item in result["comparisons_holm"]:
            comparisons.append(item)


    lines = [
        "# Paired Statistical Analysis - RCAEval full2",
        "",
        "This report analyses existing per-case CSV outputs; it does not rerun experiments.",
        "",
        f"- Bootstrap resamples: {args.bootstrap}",
        f"- Random seed: {args.seed}",
        "- Confidence intervals: paired percentile bootstrap, 95%.",
        "- Hit@k tests: exact two-sided McNemar.",
        "- MRR test: Wilcoxon signed-rank.",
        "- Multiplicity: Holm correction across the four metrics within each method comparison.",
        "",
        "Positive mean deltas favor the method named in the comparison.",
        "",
        "| Baseline | Method | Metric | Paired n | Mean delta | 95% CI low | 95% CI high | Raw p | Holm p | Wins | Losses | Ties |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]

    for item in comparisons:
        lines.append(
            f"| {item['method_a']} | {item['method_b']} | {item['metric']} "
            f"| {item['n_paired']} | {fmt(item['delta_mean_b_minus_a'])} "
            f"| {fmt(item['ci95_low'])} | {fmt(item['ci95_high'])} "
            f"| {fmt(item['pvalue'])} | {fmt(item.get('pvalue_holm'))} "
            f"| {item['wins']} | {item['losses']} | {item['ties']} |"
        )

    lines.extend(
        [
            "",
            "## Interpretation notes",
            "",
            "- Confidence intervals describe uncertainty in the paired mean difference.",
            "- Holm-adjusted p-values address multiple testing within each method's four-metric family.",
            "- Statistical significance does not establish practical importance or causal validity.",
            "- This analysis only covers the cases present in both files for each comparison.",
            "",
        ]
    )

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote paired analysis: {output}")
    print(f"Comparisons written: {len(comparisons)}")


if __name__ == "__main__":
    main()
