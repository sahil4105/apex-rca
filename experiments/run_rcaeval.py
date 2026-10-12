"""Evaluate APEX-RCA methods on RCAEval.

This runner does not overwrite results/baseline_rcaeval.csv, which remains
the frozen original-script artifact.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apex_rca.config import ExperimentConfig, default_rcaeval_dir, default_results_dir
from apex_rca.data_loader import load_case, load_index
from apex_rca.evaluation import (
    EVALUATION_METRICS,
    apply_holm_correction,
    compare_method_dataframes,
    paired_metric_comparison,
    summarize_results,
)
from apex_rca.pipeline import MethodName, diagnose_case

ALL_METHODS: tuple[MethodName, ...] = (
    "anomaly_only",
    "metrics_graph",
    "metrics_logs_traces",
    "full",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run RCAEval RCA experiments.")
    parser.add_argument(
        "--method",
        default="anomaly_only",
        help="anomaly_only | metrics_graph | metrics_logs_traces | full | all",
    )
    parser.add_argument("--limit", type=int, default=0, help="0 = all cases.")
    parser.add_argument("--suite", default="", help="Optional suite filter, e.g. RE3.")
    parser.add_argument("--system", default="", help="Optional system_name filter.")
    parser.add_argument("--graph-mode", default="auto")
    parser.add_argument("--graph-weight", type=float, default=0.30)
    parser.add_argument("--extra-weight", type=float, default=0.25)
    parser.add_argument("--data-dir", default=str(default_rcaeval_dir()))
    parser.add_argument("--results-dir", default=str(default_results_dir()))
    parser.add_argument("--tag", default="v1", help="Output filename tag.")
    return parser.parse_args()


def selected_methods(name: str) -> tuple[MethodName, ...]:
    if name == "all":
        return ALL_METHODS
    if name not in ALL_METHODS:
        raise ValueError(f"Unknown method: {name}")
    return (name,)  # type: ignore[return-value]


def print_summary(label: str, frame: pd.DataFrame) -> None:
    print("\n" + "=" * 64)
    print(label)
    print("=" * 64)
    print(f"Evaluated cases: {len(frame)}")
    if frame.empty:
        return
    print(f"Hit@1: {frame['hit1'].mean():.4f}  (n={len(frame)})")
    print(f"Hit@3: {frame['hit3'].mean():.4f}")
    print(f"Hit@5: {frame['hit5'].mean():.4f}")
    print(f"MRR:   {frame['mrr'].mean():.4f}")
    print(f"Mean runtime s/case: {frame['runtime_s'].mean():.3f}")
    print("\nBy suite:")
    print(
        frame.groupby("suite")[["hit1", "hit3", "hit5", "mrr"]]
        .mean()
        .round(4)
        .to_string()
    )
    print("\nBy system:")
    print(
        frame.groupby("system")[["hit1", "hit3", "hit5", "mrr"]]
        .mean()
        .round(4)
        .to_string()
    )


def compare_frames(
    frame_a: pd.DataFrame,
    frame_b: pd.DataFrame,
    *,
    label_a: str,
    label_b: str,
    seed: int,
) -> list[dict[str, object]]:
    """Compare two methods on their exact case intersection with full diagnostics."""
    res = compare_method_dataframes(
        frame_a,
        frame_b,
        label_a=label_a,
        label_b=label_b,
        seed=seed,
    )
    return res["comparisons"]


def main() -> None:
    args = parse_args()
    methods = selected_methods(args.method)
    data_dir = Path(args.data_dir)
    results_dir = Path(args.results_dir)
    results_dir.mkdir(parents=True, exist_ok=True)

    config = ExperimentConfig(
        name=f"rcaeval_{args.tag}",
        graph_mode=args.graph_mode,
        graph_weight=args.graph_weight,
        extra_weight=args.extra_weight,
        data_dir=str(data_dir),
        results_dir=str(results_dir),
    )

    index = load_index(data_dir)
    cases = index.sort_values("case").reset_index(drop=True)
    if args.suite:
        cases = cases[cases["suite"].astype(str) == args.suite]
    if args.system:
        cases = cases[cases["system_name"].astype(str) == args.system]
    if args.limit > 0:
        cases = cases.head(args.limit)
    cases = cases.reset_index(drop=True)

    print("APEX-RCA RCAEval evaluation")
    print(f"Methods: {', '.join(methods)}")
    print(f"Cases selected: {len(cases)}")
    print(f"Task: {config.task}")
    print(f"Graph mode={config.graph_mode} graph_weight={config.graph_weight}")

    needs_logs = any(m in {"metrics_logs_traces", "full"} for m in methods)
    needs_traces = any(m in {"metrics_graph", "metrics_logs_traces", "full"} for m in methods)
    traces_for_graph_only = needs_traces and not needs_logs

    by_method: dict[str, list[dict]] = {m: [] for m in methods}
    skipped: list[dict[str, str]] = []
    wall_start = time.perf_counter()

    for i, (_, row) in enumerate(cases.iterrows(), start=1):
        bundle = load_case(
            data_dir,
            row,
            load_logs=needs_logs,
            load_traces=needs_traces,
            traces_for_graph_only=traces_for_graph_only and "full" not in methods
            and "metrics_logs_traces" not in methods,
        )
        for method in methods:
            result = diagnose_case(bundle, config, method)
            if result.skip_reason:
                skipped.append(
                    {
                        "case": result.case,
                        "method": method,
                        "reason": result.skip_reason,
                    }
                )
            else:
                by_method[method].append(result.to_row())
        if i % 10 == 0 or i == len(cases):
            print(f"Processed {i}/{len(cases)} cases")

    elapsed = time.perf_counter() - wall_start
    config_path = results_dir / f"config_{args.tag}.json"
    config_path.write_text(json.dumps(config.to_dict(), indent=2), encoding="utf-8")

    summaries: dict[str, object] = {
        "config": config.to_dict(),
        "n_indexed_selected": int(len(cases)),
        "wall_time_s": elapsed,
        "methods": {},
    }

    frames: dict[str, pd.DataFrame] = {}
    for method, rows in by_method.items():
        frame = pd.DataFrame(rows)
        frames[method] = frame
        out = results_dir / f"{method}_{args.tag}.csv"
        if not frame.empty:
            frame.to_csv(out, index=False)
        else:
            pd.DataFrame(columns=["case", "method"]).to_csv(out, index=False)
        method_skips = [s for s in skipped if s["method"] == method]
        print_summary(f"{method}  (saved {out.name})", frame)
        print(f"Skipped: {len(method_skips)}")
        summaries["methods"][method] = {
            "n_evaluated": int(len(frame)),
            "n_skipped": len(method_skips),
            "output": str(out),
            "summary": summarize_results(frame, seed=config.seed) if not frame.empty else {},
        }

    skip_path = results_dir / f"skipped_{args.tag}.csv"
    pd.DataFrame(skipped).to_csv(skip_path, index=False)

    if "anomaly_only" in frames and "metrics_graph" in frames:
        graph_comparisons = compare_frames(
            frames["anomaly_only"],
            frames["metrics_graph"],
            label_a="anomaly_only",
            label_b="metrics_graph",
            seed=config.seed,
        )
        summaries["paired_anomaly_vs_graph"] = graph_comparisons
        hit1 = graph_comparisons[0]
        summaries["mcnemar_hit1_anomaly_vs_graph"] = {
            "n_paired": hit1["n_paired"],
            "a_correct_b_wrong": hit1["a_correct_b_wrong"],
            "a_wrong_b_correct": hit1["a_wrong_b_correct"],
            "pvalue": hit1["pvalue"],
        }

    if "anomaly_only" in frames and "full" in frames:
        full_comparisons = compare_frames(
            frames["anomaly_only"],
            frames["full"],
            label_a="anomaly_only",
            label_b="full",
            seed=config.seed,
        )
        summaries["paired_anomaly_vs_full"] = full_comparisons
        hit1 = full_comparisons[0]
        summaries["mcnemar_hit1_anomaly_vs_full"] = {
            "n_paired": hit1["n_paired"],
            "a_correct_b_wrong": hit1["a_correct_b_wrong"],
            "a_wrong_b_correct": hit1["a_wrong_b_correct"],
            "pvalue": hit1["pvalue"],
        }

    comparison_family: list[dict[str, object]] = []
    for key, label in (
        (("anomaly_only", "metrics_graph"), "anomaly_vs_graph"),
        (("anomaly_only", "metrics_logs_traces"), "anomaly_vs_logs_traces"),
        (("anomaly_only", "full"), "anomaly_vs_full"),
    ):
        if key[0] in frames and key[1] in frames:
            comparison_family.extend(
                compare_frames(
                    frames[key[0]],
                    frames[key[1]],
                    label_a=key[0],
                    label_b=key[1],
                    seed=config.seed,
                )
            )
    summaries["paired_comparisons_holm"] = apply_holm_correction(comparison_family)
    comparison_path = results_dir / f"comparisons_{args.tag}.json"
    comparison_path.write_text(
        json.dumps(summaries["paired_comparisons_holm"], indent=2),
        encoding="utf-8",
    )

    summary_path = results_dir / f"summary_{args.tag}.json"
    summary_path.write_text(json.dumps(summaries, indent=2), encoding="utf-8")
    print(f"\nWall time: {elapsed:.1f}s")
    print(f"Config: {config_path}")
    print(f"Summary: {summary_path}")
    print(f"Comparisons: {comparison_path}")
    print(f"Skipped report: {skip_path}")


if __name__ == "__main__":
    main()
