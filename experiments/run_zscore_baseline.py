"""Evaluate a conventional z-score baseline on RCAEval."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apex_rca.config import ExperimentConfig, default_rcaeval_dir, default_results_dir
from apex_rca.data_loader import load_case
from apex_rca.evaluation import case_metrics
from apex_rca.metric_parsing import service_metric_columns
from apex_rca.preprocessing import inject_in_recorded_window, split_by_inject_time
from apex_rca.ranking import rank_services


def zscore_service_scores(
    reference: pd.DataFrame,
    observed: pd.DataFrame,
    mapping: dict[str, list[str]],
    *,
    min_samples: int,
    cap: float = 20.0,
    top_k_metrics: int = 3,
) -> dict[str, float]:
    """Rank services using mean absolute post-window z-scores."""
    scores: dict[str, float] = {}

    for service, columns in mapping.items():
        effects: list[float] = []

        for column in columns:
            if column not in reference or column not in observed:
                continue

            ref = pd.to_numeric(reference[column], errors="coerce").to_numpy(dtype=float)
            obs = pd.to_numeric(observed[column], errors="coerce").to_numpy(dtype=float)

            ref = ref[np.isfinite(ref)]
            obs = obs[np.isfinite(obs)]

            if len(ref) < min_samples or len(obs) < min_samples:
                continue

            mean = float(np.mean(ref))
            std = float(np.std(ref, ddof=0))

            if not np.isfinite(std):
                continue

            # A zero-variance reference cannot define a conventional z-score.
            # Use a small scale floor to keep the calculation finite.
            scale_floor = max(abs(mean) * 1e-6, 1e-6)
            scale = max(std, scale_floor)

            effect = abs(float(np.median(obs)) - mean) / scale
            if np.isfinite(effect):
                effects.append(min(effect, cap))

        if effects:
            effects.sort(reverse=True)
            scores[service] = float(np.mean(effects[:top_k_metrics]))

    return scores


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate the z-score RCA baseline.")
    parser.add_argument("--limit", type=int, default=0, help="0 = all cases.")
    parser.add_argument("--suite", default="", help="Optional suite filter, e.g. RE3.")
    parser.add_argument("--system", default="", help="Optional system_name filter.")
    parser.add_argument("--data-dir", default=str(default_rcaeval_dir()))
    parser.add_argument("--results-dir", default=str(default_results_dir()))
    parser.add_argument("--tag", default="zscore_v1")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    results_dir = Path(args.results_dir)
    results_dir.mkdir(parents=True, exist_ok=True)

    config = ExperimentConfig(
        name=f"rcaeval_{args.tag}",
        data_dir=str(data_dir),
        results_dir=str(results_dir),
    )

    from apex_rca.data_loader import load_index

    cases = load_index(data_dir).sort_values("case").reset_index(drop=True)

    if args.suite:
        cases = cases[cases["suite"].astype(str) == args.suite]
    if args.system:
        cases = cases[cases["system_name"].astype(str) == args.system]
    if args.limit > 0:
        cases = cases.head(args.limit)

    rows: list[dict] = []
    skipped: list[dict] = []
    started = time.perf_counter()

    print(f"Z-score baseline: {len(cases)} selected cases")

    for i, (_, row) in enumerate(cases.iterrows(), start=1):
        case_started = time.perf_counter()
        bundle = load_case(data_dir, row, load_logs=False, load_traces=False)

        metrics = bundle.metrics
        case = str(row["case"])
        truth = str(row.get("root_cause_service", "")).strip()
        suite = str(row.get("suite", ""))
        system = str(row.get("system_name", row.get("system", "")))
        fault = str(row.get("fault", ""))

        reason = None
        if "time" not in metrics.columns:
            reason = "time column missing"
        elif "inject_time" not in row.index or pd.isna(row["inject_time"]):
            reason = "injection timestamp missing"
        elif not inject_in_recorded_window(row):
            reason = "inject_time outside recorded [time_start, time_end] window"

        if reason is None:
            reference, observed = split_by_inject_time(
                metrics, float(row["inject_time"])
            )

            if (
                len(reference) < config.min_window_samples
                or len(observed) < config.min_window_samples
            ):
                reason = "insufficient pre/post-injection samples"
            else:
                mapping = service_metric_columns(metrics)
                scores = zscore_service_scores(
                    reference,
                    observed,
                    mapping,
                    min_samples=config.min_window_samples,
                    cap=config.anomaly_effect_cap,
                    top_k_metrics=config.top_k_metrics,
                )
                if not scores:
                    reason = "no usable service metrics"

        if reason is not None:
            skipped.append({"case": case, "reason": reason})
        else:
            ranked = rank_services(scores)
            names = [name for name, _ in ranked]
            evaluated = case_metrics(names, truth)

            rows.append({
                "case": case,
                "method": "zscore",
                "suite": suite,
                "system": system,
                "fault": fault,
                "root_cause": truth,
                "hit1": int(evaluated["hit1"]),
                "hit3": int(evaluated["hit3"]),
                "hit5": int(evaluated["hit5"]),
                "mrr": float(evaluated["mrr"]),
                "rank": evaluated["rank"],
                "runtime_s": time.perf_counter() - case_started,
                "top3": ", ".join(
                    f"{name} ({score:.2f})" for name, score in ranked[:3]
                ),
                "ranked_names": "|".join(names),
            })

        if i % 10 == 0 or i == len(cases):
            print(f"Processed {i}/{len(cases)} cases")

    frame = pd.DataFrame(rows)
    output = results_dir / f"zscore_{args.tag}.csv"
    frame.to_csv(output, index=False)

    skip_output = results_dir / f"zscore_skipped_{args.tag}.csv"
    pd.DataFrame(skipped, columns=["case", "reason"]).to_csv(
        skip_output, index=False
    )

    print("\nZ-score baseline results")
    print(f"Evaluated: {len(frame)}")
    print(f"Skipped: {len(skipped)}")
    if not frame.empty:
        print(f"Hit@1: {frame['hit1'].mean():.4f}")
        print(f"Hit@3: {frame['hit3'].mean():.4f}")
        print(f"Hit@5: {frame['hit5'].mean():.4f}")
        print(f"MRR:   {frame['mrr'].mean():.4f}")
        print("\nBy suite:")
        print(frame.groupby("suite")[["hit1", "hit3", "hit5", "mrr"]].mean().round(4))
    print(f"\nWall time: {time.perf_counter() - started:.1f}s")
    print(f"Results: {output}")
    print(f"Skipped report: {skip_output}")


if __name__ == "__main__":
    main()
