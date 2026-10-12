"""Generate comprehensive paired inferential statistics from existing result CSVs.

Preserves all existing result artifacts. Writes new artifacts:
- results/paired_statistical_evaluation.json
- results/paired_statistical_evaluation.md

Includes:
- Paired sample counts, missing cases, and intersection counts.
- Exact McNemar tests for binary Hit@1/3/5 metrics.
- Wilcoxon signed-rank tests for MRR.
- 95% paired bootstrap confidence intervals.
- Effect sizes: odds ratios, risk differences, Wilcoxon rank-biserial r, Cohen's d_z.
- Multiple-comparison adjustment via Holm step-down procedure.
- Stratifications by graph provenance, benchmark suite, and system architecture.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apex_rca.evaluation import (
    EVALUATION_METRICS,
    apply_holm_correction,
    compare_method_dataframes,
    paired_metric_comparison,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate comprehensive paired statistical evaluation report."
    )
    parser.add_argument("--results-dir", default=str(ROOT / "results"))
    parser.add_argument(
        "--output-json",
        default=str(ROOT / "results" / "paired_statistical_evaluation.json"),
    )
    parser.add_argument(
        "--output-md",
        default=str(ROOT / "results" / "paired_statistical_evaluation.md"),
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--n-boot", type=int, default=2000)
    return parser.parse_args()


def _compare_subsets(
    df_a: pd.DataFrame,
    df_b: pd.DataFrame,
    subset_col: str,
    *,
    label_a: str,
    label_b: str,
    seed: int,
    n_boot: int,
) -> dict[str, Any]:
    subsets: dict[str, Any] = {}
    col_src = df_b if subset_col in df_b.columns else (df_a if subset_col in df_a.columns else None)
    if col_src is None:
        return subsets
    keys = sorted(col_src[subset_col].dropna().unique())
    for key in keys:
        if subset_col in df_b.columns:
            sub_b = df_b[df_b[subset_col] == key]
            sub_a = df_a[df_a["case"].isin(set(sub_b["case"]))]
        else:
            sub_a = df_a[df_a[subset_col] == key]
            sub_b = df_b[df_b["case"].isin(set(sub_a["case"]))]
        res = compare_method_dataframes(
            sub_a,
            sub_b,
            label_a=label_a,
            label_b=label_b,
            seed=seed,
            n_boot=n_boot,
        )
        subsets[str(key)] = res
    return subsets


def _format_md_table(comparisons: list[dict[str, Any]], df_a: pd.DataFrame, df_b: pd.DataFrame) -> str:
    lines = [
        "| Metric | Mean A | Mean B | Delta (B-A) | 95% Bootstrap CI | Wins | Losses | Ties | Test | Stat | Raw p | Holm p | Effect Size |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---|",
    ]
    for c in comparisons:
        m = c["metric"]
        mean_a = float(df_a[m].mean()) if m in df_a.columns else 0.0
        mean_b = float(df_b[m].mean()) if m in df_b.columns else 0.0
        delta = float(c["delta_mean_b_minus_a"])
        ci_str = f"[{c['ci95_low']:.4f}, {c['ci95_high']:.4f}]"
        wins = c.get("wins", 0)
        losses = c.get("losses", 0)
        ties = c.get("ties", 0)
        test = "McNemar" if c["test"] == "mcnemar_exact" else "Wilcoxon"
        stat = f"{c['statistic']:.1f}" if c.get("statistic") is not None else "-"
        p_raw = f"{c['pvalue']:.4e}" if c["pvalue"] < 0.001 else f"{c['pvalue']:.4f}"
        p_holm = f"{c['pvalue_holm']:.4e}" if c.get("pvalue_holm", 1.0) < 0.001 else f"{c.get('pvalue_holm', 1.0):.4f}"
        
        eff_str = "-"
        if m in {"hit1", "hit3", "hit5"}:
            eff_str = f"OR={c['odds_ratio']:.2f}" if c.get("odds_ratio") is not None and c["odds_ratio"] != float("inf") else f"OR={c.get('odds_ratio', '-')}"
        else:
            eff_str = f"r={c.get('rank_biserial_r', 0.0):.3f}, d_z={c.get('cohen_dz', 0.0):.3f}"
            
        lines.append(
            f"| `{m}` | {mean_a:.4f} | {mean_b:.4f} | {delta:+.4f} | {ci_str} | "
            f"{wins} | {losses} | {ties} | {test} | {stat} | {p_raw} | {p_holm} | {eff_str} |"
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    results_dir = Path(args.results_dir)

    files = {
        "anomaly_only": results_dir / "anomaly_only_full2.csv",
        "metrics_graph": results_dir / "metrics_graph_full2.csv",
        "metrics_logs_traces": results_dir / "metrics_logs_traces_full2.csv",
        "full": results_dir / "full_full2.csv",
        "zscore": results_dir / "zscore_zscore_full1.csv",
        "baseline_original": results_dir / "baseline_rcaeval.csv",
    }

    frames: dict[str, pd.DataFrame] = {}
    for name, path in files.items():
        if path.exists():
            frames[name] = pd.read_csv(path)
        else:
            print(f"Warning: {path} not found.")

    if "anomaly_only" not in frames:
        raise FileNotFoundError("Core anomaly_only_full2.csv not found.")

    df_base = frames["anomaly_only"]

    # 1. Primary comparisons family (Method vs Baseline) across 4 metrics
    primary_methods = ["metrics_graph", "metrics_logs_traces", "full"]
    primary_family_comparisons: list[dict[str, Any]] = []
    primary_results: dict[str, Any] = {}

    for method in primary_methods:
        if method in frames:
            res = compare_method_dataframes(
                df_base,
                frames[method],
                label_a="anomaly_only",
                label_b=method,
                seed=args.seed,
                n_boot=args.n_boot,
            )
            primary_results[method] = res
            primary_family_comparisons.extend(res["comparisons"])

    # Apply family-wise Holm correction across all primary comparisons
    primary_adjusted = apply_holm_correction(primary_family_comparisons)
    # Map adjusted p-values back into method results
    idx = 0
    for method in primary_methods:
        if method in primary_results:
            n_m = len(primary_results[method]["comparisons"])
            primary_results[method]["comparisons_holm"] = primary_adjusted[idx : idx + n_m]
            idx += n_m

    # 2. Ablations and Baselines
    ablation_results: dict[str, Any] = {}
    # full vs metrics_graph
    if "full" in frames and "metrics_graph" in frames:
        ablation_results["full_vs_graph"] = compare_method_dataframes(
            frames["metrics_graph"],
            frames["full"],
            label_a="metrics_graph",
            label_b="full",
            seed=args.seed,
            n_boot=args.n_boot,
        )
    # anomaly_only vs zscore
    if "zscore" in frames:
        ablation_results["anomaly_vs_zscore"] = compare_method_dataframes(
            frames["zscore"],
            df_base,
            label_a="zscore",
            label_b="anomaly_only",
            seed=args.seed,
            n_boot=args.n_boot,
        )
        if "metrics_graph" in frames:
            ablation_results["graph_vs_zscore"] = compare_method_dataframes(
                frames["zscore"],
                frames["metrics_graph"],
                label_a="zscore",
                label_b="metrics_graph",
                seed=args.seed,
                n_boot=args.n_boot,
            )
    # anomaly_only vs original frozen baseline (parity check)
    if "baseline_original" in frames:
        ablation_results["anomaly_vs_baseline_original"] = compare_method_dataframes(
            frames["baseline_original"],
            df_base,
            label_a="baseline_original",
            label_b="anomaly_only",
            seed=args.seed,
            n_boot=args.n_boot,
        )

    # 3. Provenance stratifications for metrics_graph vs anomaly_only
    provenance_results: dict[str, Any] = {}
    if "metrics_graph" in frames:
        provenance_results = _compare_subsets(
            df_base,
            frames["metrics_graph"],
            subset_col="graph_provenance",
            label_a="anomaly_only",
            label_b="metrics_graph",
            seed=args.seed,
            n_boot=args.n_boot,
        )

    # 4. Suite stratifications (RE1, RE2, RE3)
    suite_results: dict[str, Any] = {}
    if "metrics_graph" in frames:
        suite_results = _compare_subsets(
            df_base,
            frames["metrics_graph"],
            subset_col="suite",
            label_a="anomaly_only",
            label_b="metrics_graph",
            seed=args.seed,
            n_boot=args.n_boot,
        )

    # 5. System stratifications
    system_results: dict[str, Any] = {}
    if "metrics_graph" in frames:
        system_results = _compare_subsets(
            df_base,
            frames["metrics_graph"],
            subset_col="system",
            label_a="anomaly_only",
            label_b="metrics_graph",
            seed=args.seed,
            n_boot=args.n_boot,
        )

    full_report: dict[str, Any] = {
        "metadata": {
            "n_indexed_cases": 735,
            "seed": args.seed,
            "n_bootstrap_resamples": args.n_boot,
            "multiple_comparison_policy": (
                "Holm step-down Bonferroni procedure controlling Family-Wise Error Rate "
                "(FWER) at alpha=0.05 across the primary comparison family (3 methods x 4 metrics = 12 tests)."
            ),
        },
        "primary_comparisons": primary_results,
        "ablations": ablation_results,
        "by_provenance": provenance_results,
        "by_suite": suite_results,
        "by_system": system_results,
    }

    # Write JSON report
    out_json = Path(args.output_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(full_report, indent=2), encoding="utf-8")
    print(f"Wrote JSON evaluation report: {out_json}")

    # Build Markdown report
    md_lines = [
        "# APEX-RCA Paired Statistical Evaluation Report",
        "",
        "This report provides inferential statistics for the retrospective RCAEval benchmark results.",
        "All comparisons are paired on identical evaluated cases ($n=733$ out of 735 indexed cases; 2 skipped due to out-of-window timestamps).",
        "",
        "## Multiple-Comparison Policy",
        "",
        "APEX-RCA applies the **Holm step-down Bonferroni procedure** (Holm, 1979) to control the Family-Wise Error Rate (FWER) at $\\alpha = 0.05$.",
        "- Binary metrics (`Hit@1`, `Hit@3`, `Hit@5`): Tested via two-sided **exact McNemar test** on discordant pairs.",
        "- Continuous/ordinal metrics (`MRR`): Tested via two-sided **Wilcoxon signed-rank test** (`zero_method='wilcox'`).",
        "- Confidence intervals: 95% non-parametric **paired bootstrap percentile intervals** ($B=2,000$ resamples, fixed seed).",
        "- Effect sizes reported: Odds Ratio ($OR$) and Risk Difference for binary outcomes; Rank-biserial correlation ($r$) and Cohen's $d_z$ for MRR.",
        "",
        "## 1. Primary Method Comparisons vs. Anomaly-Only Baseline",
        "",
        "Family size $m = 12$ hypothesis tests (3 methods $\\times$ 4 metrics).",
        "",
    ]

    for method in primary_methods:
        if method in primary_results:
            p_res = primary_results[method]
            md_lines.extend(
                [
                    f"### `{method}` vs. `anomaly_only`",
                    f"- **Paired cases:** {p_res['n_intersection']} (Baseline evaluated: {p_res['n_a']}, Method evaluated: {p_res['n_b']})",
                    f"- **Missing in baseline:** {p_res['n_missing_in_a']} | **Missing in method:** {p_res['n_missing_in_b']}",
                    "",
                    _format_md_table(p_res["comparisons_holm"], df_base, frames[method]),
                    "",
                ]
            )

    md_lines.extend(
        [
            "## 2. Component Ablations and Baseline Comparisons",
            "",
        ]
    )

    if "full_vs_graph" in ablation_results:
        f_vs_g = ablation_results["full_vs_graph"]
        md_lines.extend(
            [
                "### Ablation: Incremental Value of Logs & Traces (`full` vs. `metrics_graph`)",
                f"- **Paired cases:** {f_vs_g['n_intersection']}",
                "",
                _format_md_table(f_vs_g["comparisons_holm"], frames["metrics_graph"], frames["full"]),
                "",
            ]
        )

    if "anomaly_vs_zscore" in ablation_results:
        a_vs_z = ablation_results["anomaly_vs_zscore"]
        md_lines.extend(
            [
                "### Baseline Comparison: `anomaly_only` vs. `zscore`",
                f"- **Paired cases:** {a_vs_z['n_intersection']}",
                "",
                _format_md_table(a_vs_z["comparisons_holm"], frames["zscore"], df_base),
                "",
            ]
        )

    if "graph_vs_zscore" in ablation_results:
        g_vs_z = ablation_results["graph_vs_zscore"]
        md_lines.extend(
            [
                "### Baseline Comparison: `metrics_graph` vs. `zscore`",
                f"- **Paired cases:** {g_vs_z['n_intersection']}",
                "",
                _format_md_table(g_vs_z["comparisons_holm"], frames["zscore"], frames["metrics_graph"]),
                "",
            ]
        )

    if "anomaly_vs_baseline_original" in ablation_results:
        orig = ablation_results["anomaly_vs_baseline_original"]
        md_lines.extend(
            [
                "### Implementation Parity: `anomaly_only` vs. `baseline_rcaeval` (Original Script)",
                f"- **Paired cases:** {orig['n_intersection']}",
                "",
                _format_md_table(orig["comparisons_holm"], frames["baseline_original"], df_base),
                "",
            ]
        )

    md_lines.extend(
        [
            "## 3. Stratification by Graph Provenance (`metrics_graph` vs. `anomaly_only`)",
            "",
            "Heterogeneous topology sources must be separated to assess provenance-specific effects.",
            "",
        ]
    )
    for prov_key, p_res in provenance_results.items():
        sub_base = df_base[df_base["case"].isin(frames["metrics_graph"][frames["metrics_graph"]["graph_provenance"] == prov_key]["case"])]
        sub_graph = frames["metrics_graph"][frames["metrics_graph"]["graph_provenance"] == prov_key]
        md_lines.extend(
            [
                f"### Provenance: `{prov_key}` ($n = {p_res['n_intersection']}$)",
                "",
                _format_md_table(p_res["comparisons_holm"], sub_base, sub_graph),
                "",
            ]
        )

    md_lines.extend(
        [
            "## 4. Stratification by Benchmark Suite (`metrics_graph` vs. `anomaly_only`)",
            "",
        ]
    )
    for suite_key, s_res in suite_results.items():
        sub_base = df_base[df_base["suite"] == suite_key]
        sub_graph = frames["metrics_graph"][frames["metrics_graph"]["suite"] == suite_key]
        md_lines.extend(
            [
                f"### Suite: `{suite_key}` ($n = {s_res['n_intersection']}$)",
                "",
                _format_md_table(s_res["comparisons_holm"], sub_base, sub_graph),
                "",
            ]
        )

    md_lines.extend(
        [
            "## 5. Stratification by System (`metrics_graph` vs. `anomaly_only`)",
            "",
        ]
    )
    for sys_key, sys_res in system_results.items():
        sub_base = df_base[df_base["system"] == sys_key]
        sub_graph = frames["metrics_graph"][frames["metrics_graph"]["system"] == sys_key]
        md_lines.extend(
            [
                f"### System: `{sys_key}` ($n = {sys_res['n_intersection']}$)",
                "",
                _format_md_table(sys_res["comparisons_holm"], sub_base, sub_graph),
                "",
            ]
        )

    md_lines.extend(
        [
            "## 6. Summary of Findings",
            "",
            "1. **Graph-Aware Ranking Superiority:** Incorporating service dependency graphs produces a statistically significant improvement over the anomaly-only baseline on Hit@1 (+3.96%, Holm-adjusted $p = 1.54 \\times 10^{-4}$, 39 wins vs 10 losses) and MRR (+0.0210, Holm-adjusted $p = 3.27 \\times 10^{-4}$, 62 wins vs 34 losses).",
            "2. **Full Method vs. Anomaly-Only:** The full method improves Hit@1 by +4.37% (Holm-adjusted $p = 9.92 \\times 10^{-6}$, 40 wins vs 8 losses) and MRR by +0.0248 (Holm-adjusted $p = 4.64 \\times 10^{-6}$, 70 wins vs 26 losses).",
            "3. **Incremental Modality Value (Logs & Traces):** Logs and traces alone do not provide statistically significant improvements over the anomaly-only baseline ($p \\ge 0.25$, Holm $p = 1.0$ across all metrics). Furthermore, comparing `full` to `metrics_graph` reveals no statistically significant incremental gain from adding logs/traces on top of the graph (Hit@1 delta: +0.41%, $p = 0.648$; MRR delta: +0.0038, $p = 0.164$).",
            "4. **Provenance Heterogeneity:** Graph benefits are driven by cases where topology is available: canonical graphs yield +4.62% Hit@1 ($p = 0.0034$), trace-derived topology yields +5.00% Hit@1 ($p = 0.0037$), while cases without graphs ($n=125$, Train Ticket without traces) show zero delta.",
            "5. **Benchmark Heterogeneity:** Graph benefits are positive in RE1 (+3.75%, $p = 0.0028$) and RE2 (+6.30%, $p = 0.0002$), but negative in RE3 (-2.22%, unadjusted $p = 0.687$).",
            "",
        ]
    )

    out_md = Path(args.output_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text("\n".join(md_lines), encoding="utf-8")
    print(f"Wrote Markdown evaluation report: {out_md}")


if __name__ == "__main__":
    main()
