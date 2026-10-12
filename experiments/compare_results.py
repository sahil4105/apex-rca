"""Generate a concise comparison report from existing result artifacts.

The command is read-only with respect to experiment inputs and outputs unless
the requested report path is written. It does not execute any experiment.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare existing APEX-RCA result summaries."
    )
    parser.add_argument("--results-dir", default="results")
    parser.add_argument(
        "--output",
        default="results/comparison_report.md",
    )
    return parser.parse_args()


def _method_rows(summary: dict) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for method, payload in summary.get("methods", {}).items():
        metrics = payload.get("summary", {})
        rows.append(
            {
                "method": method,
                "n_evaluated": payload.get("n_evaluated", 0),
                "n_skipped": payload.get("n_skipped", 0),
                "hit1": metrics.get("hit1", {}).get("mean"),
                "mrr": metrics.get("mrr", {}).get("mean"),
            }
        )
    return rows


def main() -> None:
    args = parse_args()
    results = Path(args.results_dir)
    summary_paths = sorted(results.glob("summary_*.json"))
    if not summary_paths:
        raise FileNotFoundError("No summary_*.json files were found.")

    lines = [
        "# Existing APEX-RCA Experiment Comparison",
        "",
        "Generated from existing summary JSON and configuration artifacts.",
        "This report does not rerun experiments or modify their CSV outputs.",
        "",
        "| Tag | Indexed | Method | Evaluated | Skipped | Hit@1 | MRR |",
        "|---|---:|---|---:|---:|---:|---:|",
    ]
    for summary_path in summary_paths:
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        tag = summary_path.stem.removeprefix("summary_")
        indexed = summary.get("n_indexed_selected", "")
        config_path = results / f"config_{tag}.json"
        config = (
            json.loads(config_path.read_text(encoding="utf-8"))
            if config_path.exists()
            else {}
        )
        for row in _method_rows(summary):
            hit1 = "" if row["hit1"] is None else f"{row['hit1']:.4f}"
            mrr = "" if row["mrr"] is None else f"{row['mrr']:.4f}"
            lines.append(
                f"| {tag} | {indexed} | {row['method']} | "
                f"{row['n_evaluated']} | {row['n_skipped']} | {hit1} | {mrr} |"
            )
        if config:
            lines.extend(
                [
                    "",
                    f"**{tag} configuration:** "
                    f"graph mode `{config.get('graph_mode')}`, "
                    f"graph weight `{config.get('graph_weight')}`, "
                    f"extra weight `{config.get('extra_weight')}`, "
                    f"seed `{config.get('seed')}`, "
                    f"graph time scope `{config.get('graph_time_scope')}`.",
                    "",
                ]
            )

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {output}")


if __name__ == "__main__":
    main()
