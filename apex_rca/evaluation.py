"""Hit@k, MRR, bootstrap intervals, and paired method comparisons."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import binomtest, wilcoxon

EVALUATION_METRICS: tuple[str, ...] = ("hit1", "hit3", "hit5", "mrr")


def reciprocal_rank(ranked_names: Sequence[str], truth: str) -> float:
    if not truth:
        return 0.0
    for index, name in enumerate(ranked_names, start=1):
        if name == truth:
            return 1.0 / index
    return 0.0


def hit_at_k(ranked_names: Sequence[str], truth: str, k: int) -> int:
    if not truth:
        return 0
    return int(truth in list(ranked_names)[:k])


def rank_of(ranked_names: Sequence[str], truth: str) -> int | None:
    try:
        return list(ranked_names).index(truth) + 1
    except ValueError:
        return None


def case_metrics(ranked_names: Sequence[str], truth: str) -> dict[str, float]:
    return {
        "hit1": hit_at_k(ranked_names, truth, 1),
        "hit3": hit_at_k(ranked_names, truth, 3),
        "hit5": hit_at_k(ranked_names, truth, 5),
        "mrr": reciprocal_rank(ranked_names, truth),
        "rank": rank_of(ranked_names, truth),
    }


def bootstrap_mean_ci(
    values: Sequence[float],
    *,
    n_boot: int = 2000,
    seed: int = 42,
    alpha: float = 0.05,
) -> tuple[float, float, float]:
    """Return (mean, lower, upper) for a bootstrap CI of the mean."""
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    if arr.size == 0:
        return float("nan"), float("nan"), float("nan")
    mean = float(arr.mean())
    rng = np.random.default_rng(seed)
    draws = rng.choice(arr, size=(n_boot, arr.size), replace=True).mean(axis=1)
    lo, hi = np.quantile(draws, [alpha / 2, 1 - alpha / 2])
    return mean, float(lo), float(hi)


def paired_bootstrap_delta_ci(
    values_a: Sequence[float],
    values_b: Sequence[float],
    *,
    n_boot: int = 2000,
    seed: int = 42,
    alpha: float = 0.05,
) -> tuple[float, float, float, int]:
    """Return mean(B-A), percentile CI, and the number of finite pairs."""
    a = np.asarray(values_a, dtype=float)
    b = np.asarray(values_b, dtype=float)
    if a.shape != b.shape:
        raise ValueError("Paired values must have the same length.")
    finite = np.isfinite(a) & np.isfinite(b)
    deltas = b[finite] - a[finite]
    if deltas.size == 0:
        return float("nan"), float("nan"), float("nan"), 0
    mean = float(deltas.mean())
    rng = np.random.default_rng(seed)
    draws = rng.choice(deltas, size=(n_boot, deltas.size), replace=True).mean(axis=1)
    lo, hi = np.quantile(draws, [alpha / 2, 1 - alpha / 2])
    return mean, float(lo), float(hi), int(deltas.size)


def mcnemar_exact(hits_a: Sequence[int], hits_b: Sequence[int]) -> dict[str, Any]:
    """Exact McNemar test on paired Hit@1 (or other binary) outcomes.

    Tests whether method B differs from method A in the discordant pairs.
    Reports wins (B=1, A=0), losses (B=0, A=1), ties (A=B), exact two-sided p-value,
    odds ratio, Haldane-Anscombe corrected odds ratio, and risk difference.
    """
    a = np.asarray(hits_a, dtype=int)
    b = np.asarray(hits_b, dtype=int)
    if a.shape != b.shape:
        raise ValueError("Paired outcomes must have the same length.")
    n01 = int(np.sum((a == 1) & (b == 0)))  # B loss: A correct, B wrong
    n10 = int(np.sum((a == 0) & (b == 1)))  # B win: A wrong, B correct
    ties = int(np.sum(a == b))
    n_disc = n01 + n10
    if n_disc == 0:
        pvalue = 1.0
    else:
        pvalue = float(binomtest(n10, n=n_disc, p=0.5, alternative="two-sided").pvalue)
    odds_ratio = float(n10 / n01) if n01 > 0 else (float("inf") if n10 > 0 else 1.0)
    haldane_or = float((n10 + 0.5) / (n01 + 0.5))
    risk_diff = float((n10 - n01) / a.size) if a.size > 0 else 0.0
    return {
        "n_paired": int(a.size),
        "wins": n10,
        "losses": n01,
        "ties": ties,
        "a_correct_b_wrong": n01,
        "a_wrong_b_correct": n10,
        "pvalue": pvalue,
        "odds_ratio": odds_ratio,
        "haldane_odds_ratio": haldane_or,
        "risk_difference": risk_diff,
    }


def holm_bonferroni(pvalues: Sequence[float]) -> list[float]:
    """Return Holm step-down adjusted p-values in the original order.

    Multiple-Comparison Policy:
    APEX-RCA applies the Holm step-down Bonferroni procedure (Holm, 1979) to control
    the Family-Wise Error Rate (FWER) at level alpha = 0.05 within each declared family
    of comparisons. For m ordered raw p-values p_(1) <= ... <= p_(m), the adjusted
    p-value is:
        p_adj_(i) = min(1.0, max_{k <= i} ((m - k + 1) * p_(k)))
    Holm-Bonferroni strictly dominates standard Bonferroni in statistical power while
    remaining robust to arbitrary dependence structures.
    """
    values = np.asarray(pvalues, dtype=float)
    if values.ndim != 1:
        raise ValueError("pvalues must be one-dimensional.")
    if np.any(~np.isfinite(values)) or np.any((values < 0) | (values > 1)):
        raise ValueError("pvalues must be finite values in [0, 1].")
    order = np.argsort(values, kind="stable")
    adjusted = np.empty(values.size, dtype=float)
    running = 0.0
    for rank, index in enumerate(order):
        candidate = float((values.size - rank) * values[index])
        running = max(running, candidate)
        adjusted[index] = min(running, 1.0)
    return adjusted.tolist()


def paired_metric_comparison(
    values_a: Sequence[float],
    values_b: Sequence[float],
    *,
    metric: str,
    seed: int = 42,
    n_boot: int = 2000,
    alpha: float = 0.05,
) -> dict[str, Any]:
    """Compare paired method outcomes using a metric-appropriate test and effect sizes."""
    if metric not in EVALUATION_METRICS:
        raise ValueError(f"Unsupported evaluation metric: {metric}")
    a = np.asarray(values_a, dtype=float)
    b = np.asarray(values_b, dtype=float)
    if a.shape != b.shape:
        raise ValueError("Paired values must have the same length.")
    finite = np.isfinite(a) & np.isfinite(b)
    a_valid = a[finite]
    b_valid = b[finite]
    mean, lo, hi, n = paired_bootstrap_delta_ci(
        a_valid,
        b_valid,
        n_boot=n_boot,
        seed=seed,
        alpha=alpha,
    )
    if metric in {"hit1", "hit3", "hit5"}:
        test = mcnemar_exact(a_valid.astype(int), b_valid.astype(int))
        test_name = "mcnemar_exact"
        wins = int(test["wins"])
        losses = int(test["losses"])
        ties = int(test["ties"])
        effect_name = "odds_ratio"
        effect_val = test["odds_ratio"]
        stat = float(wins)
        cohen_dz = None
        rank_biserial = None
    else:
        diff = b_valid - a_valid
        wins = int(np.sum(diff > 1e-9))
        losses = int(np.sum(diff < -1e-9))
        ties = int(np.sum(np.abs(diff) <= 1e-9))
        std_d = float(np.std(diff, ddof=1)) if diff.size > 1 else 0.0
        cohen_dz = float(mean / std_d) if std_d > 0 else 0.0

        if n == 0 or np.allclose(diff, 0.0):
            pvalue = 1.0
            stat = 0.0
            rank_biserial = 0.0
        else:
            w_res = wilcoxon(
                a_valid,
                b_valid,
                zero_method="wilcox",
                alternative="two-sided",
                method="auto",
            )
            pvalue = float(w_res.pvalue)
            stat = float(w_res.statistic)

            # Kerby (2014) rank-biserial correlation: r = (W+ - W-) / (W+ + W-)
            from scipy.stats import rankdata

            nz = diff[np.abs(diff) > 1e-9]
            ranks = rankdata(np.abs(nz))
            w_plus = float(np.sum(ranks[nz > 0]))
            w_minus = float(np.sum(ranks[nz < 0]))
            w_total = w_plus + w_minus
            rank_biserial = float((w_plus - w_minus) / w_total) if w_total > 0 else 0.0

        test = {
            "n_paired": n,
            "pvalue": pvalue,
            "wins": wins,
            "losses": losses,
            "ties": ties,
            "odds_ratio": None,
            "haldane_odds_ratio": None,
            "risk_difference": None,
        }
        test_name = "wilcoxon_signed_rank"
        effect_name = "rank_biserial_r"
        effect_val = rank_biserial

    return {
        "metric": metric,
        "n_paired": n,
        "delta_mean_b_minus_a": mean,
        "ci95_low": lo,
        "ci95_high": hi,
        "pvalue": float(test["pvalue"]),
        "test": test_name,
        "statistic": stat,
        "wins": wins,
        "losses": losses,
        "ties": ties,
        "a_correct_b_wrong": test.get("a_correct_b_wrong", losses),
        "a_wrong_b_correct": test.get("a_wrong_b_correct", wins),
        "effect_size_name": effect_name,
        "effect_size_value": effect_val,
        "odds_ratio": test.get("odds_ratio"),
        "haldane_odds_ratio": test.get("haldane_odds_ratio"),
        "risk_difference": test.get("risk_difference"),
        "cohen_dz": cohen_dz,
        "rank_biserial_r": rank_biserial,
    }


def apply_holm_correction(
    comparisons: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Add Holm-adjusted p-values to a comparison family."""
    if not comparisons:
        return []
    adjusted = holm_bonferroni([float(item["pvalue"]) for item in comparisons])
    return [
        {**item, "pvalue_holm": adjusted[index]}
        for index, item in enumerate(comparisons)
    ]


def compare_method_dataframes(
    frame_a: pd.DataFrame,
    frame_b: pd.DataFrame,
    *,
    label_a: str = "method_a",
    label_b: str = "method_b",
    case_col: str = "case",
    metrics: Sequence[str] = EVALUATION_METRICS,
    seed: int = 42,
    n_boot: int = 2000,
    alpha: float = 0.05,
) -> dict[str, Any]:
    """Compare two method result DataFrames on paired cases with full diagnostic reporting.

    Reports:
    - Case counts: n_a, n_b, n_intersection, n_missing_in_a, n_missing_in_b.
    - Missing cases list for full auditability.
    - Paired metric comparisons for each metric (Hit@1, Hit@3, Hit@5, MRR).
    - Holm-adjusted p-values across the family.
    """
    if frame_a.empty or frame_b.empty:
        return {
            "method_a": label_a,
            "method_b": label_b,
            "n_a": int(len(frame_a)),
            "n_b": int(len(frame_b)),
            "n_intersection": 0,
            "n_missing_in_a": int(len(frame_b)),
            "n_missing_in_b": int(len(frame_a)),
            "missing_in_a": frame_b[case_col].tolist() if not frame_b.empty and case_col in frame_b.columns else [],
            "missing_in_b": frame_a[case_col].tolist() if not frame_a.empty and case_col in frame_a.columns else [],
            "comparisons": [],
            "comparisons_holm": [],
        }

    if frame_a[case_col].duplicated().any():
        raise ValueError(f"Duplicate cases found in {label_a}")
    if frame_b[case_col].duplicated().any():
        raise ValueError(f"Duplicate cases found in {label_b}")

    cases_a = set(frame_a[case_col].astype(str))
    cases_b = set(frame_b[case_col].astype(str))
    missing_in_a = sorted(cases_b - cases_a)
    missing_in_b = sorted(cases_a - cases_b)

    merged = frame_a.merge(
        frame_b,
        on=case_col,
        suffixes=("_a", "_b"),
        how="inner",
        validate="one_to_one",
    )

    comparisons: list[dict[str, Any]] = []
    for metric in metrics:
        col_a = f"{metric}_a"
        col_b = f"{metric}_b"
        if col_a not in merged.columns or col_b not in merged.columns:
            continue
        item = paired_metric_comparison(
            merged[col_a],
            merged[col_b],
            metric=metric,
            seed=seed,
            n_boot=n_boot,
            alpha=alpha,
        )
        item.update(
            {
                "method_a": label_a,
                "method_b": label_b,
                "n_a": int(len(frame_a)),
                "n_b": int(len(frame_b)),
                "n_intersection": int(len(merged)),
                "n_missing_in_a": len(missing_in_a),
                "n_missing_in_b": len(missing_in_b),
            }
        )
        comparisons.append(item)

    comparisons_holm = apply_holm_correction(comparisons)
    return {
        "method_a": label_a,
        "method_b": label_b,
        "n_a": int(len(frame_a)),
        "n_b": int(len(frame_b)),
        "n_intersection": int(len(merged)),
        "n_missing_in_a": len(missing_in_a),
        "n_missing_in_b": len(missing_in_b),
        "missing_in_a": missing_in_a,
        "missing_in_b": missing_in_b,
        "comparisons": comparisons,
        "comparisons_holm": comparisons_holm,
    }


def summarize_results(
    frame: pd.DataFrame,
    *,
    seed: int = 42,
    group_cols: tuple[str, ...] = ("suite", "system", "fault"),
) -> dict[str, Any]:
    """Build overall and grouped summaries with bootstrap CIs for Hit@1 and MRR."""
    n = int(len(frame))
    summary: dict[str, Any] = {"n_evaluated": n}
    if n == 0:
        return summary

    for metric in EVALUATION_METRICS:
        mean, lo, hi = bootstrap_mean_ci(frame[metric].tolist(), seed=seed)
        summary[metric] = {"mean": mean, "ci95_low": lo, "ci95_high": hi}

    grouped: dict[str, Any] = {}
    for col in group_cols:
        if col not in frame.columns:
            continue
        rows = []
        for key, part in frame.groupby(col, dropna=False):
            item = {"group": str(key), "n": int(len(part))}
            for metric in EVALUATION_METRICS:
                item[metric] = float(part[metric].mean())
            rows.append(item)
        grouped[col] = rows
    summary["by"] = grouped
    return summary
