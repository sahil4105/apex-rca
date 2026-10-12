"""Render docs/results.md from saved experiment CSVs. Does not invent numbers."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apex_rca.evaluation import bootstrap_mean_ci


def _table(frame: pd.DataFrame, group: str | None = None) -> str:
    if frame.empty:
        return "_No evaluated rows._\n"
    if group:
        stats = (
            frame.groupby(group)[["hit1", "hit3", "hit5", "mrr"]]
            .mean()
            .join(frame.groupby(group).size().rename("n"))
            .reset_index()
        )
        cols = [group, "n", "hit1", "hit3", "hit5", "mrr"]
    else:
        stats = pd.DataFrame(
            [
                {
                    "split": "overall",
                    "n": len(frame),
                    "hit1": frame["hit1"].mean(),
                    "hit3": frame["hit3"].mean(),
                    "hit5": frame["hit5"].mean(),
                    "mrr": frame["mrr"].mean(),
                }
            ]
        )
        cols = ["split", "n", "hit1", "hit3", "hit5", "mrr"]
    lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join("---" for _ in cols) + " |"]
    for _, row in stats.iterrows():
        cells = []
        for col in cols:
            val = row[col]
            if col in {"hit1", "hit3", "hit5", "mrr"}:
                cells.append(f"{float(val):.4f}")
            else:
                cells.append(str(val))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


def _ci_line(frame: pd.DataFrame, seed: int = 42) -> str:
    if frame.empty:
        return ""
    h_mean, h_lo, h_hi = bootstrap_mean_ci(frame["hit1"], seed=seed)
    m_mean, m_lo, m_hi = bootstrap_mean_ci(frame["mrr"], seed=seed)
    return (
        f"Hit@1 {h_mean:.4f} (95% bootstrap CI {h_lo:.4f}–{h_hi:.4f}); "
        f"MRR {m_mean:.4f} (95% CI {m_lo:.4f}–{m_hi:.4f}); n={len(frame)}.\n"
    )


def main() -> None:
    results = ROOT / "results"
    docs = ROOT / "docs"
    docs.mkdir(exist_ok=True)
    parts = [
        "# Results",
        "",
        "Generated from CSV artifacts by `experiments/write_results_md.py`.",
        "Denominators are evaluated cases. Skipped cases are excluded.",
        "",
        "## Frozen original baseline (`results/baseline_rcaeval.csv`)",
        "",
    ]
    baseline = results / "baseline_rcaeval.csv"
    if baseline.exists():
        frame = pd.read_csv(baseline)
        parts += [_table(frame), _ci_line(frame), "### By suite", _table(frame, "suite")]
        if "system" in frame.columns:
            parts += ["### By system", _table(frame, "system")]
        skip = results / "baseline_skipped.csv"
        if skip.exists():
            skipped = pd.read_csv(skip)
            parts += [
                f"Skipped cases: **{len(skipped)}** (see `results/baseline_skipped.csv`).",
                "",
            ]
    else:
        parts.append("Baseline CSV not found.\n")

    for method in ("anomaly_only_v1", "metrics_graph_v1", "metrics_logs_traces_v1", "full_v1"):
        path = results / f"{method}.csv"
        parts += [f"## Packaged method `{method}`", ""]
        if not path.exists():
            parts.append("Not measured yet.\n")
            continue
        frame = pd.read_csv(path)
        parts += [_table(frame), _ci_line(frame), "### By suite", _table(frame, "suite")]
        if "system" in frame.columns:
            parts += ["### By system", _table(frame, "system")]
        if "fault" in frame.columns:
            parts += ["### By fault", _table(frame, "fault")]

    re3 = results / "re3_anomaly_audit.csv"
    parts += ["## RE3 anomaly-signal audit", ""]
    if re3.exists():
        frame = pd.read_csv(re3)
        valid = frame[frame["skipped"].fillna("") == ""] if "skipped" in frame.columns else frame
        parts.append(f"Evaluated RE3 rows in audit file: {len(valid)}.\n")
        if not valid.empty and "hit1" in valid.columns:
            parts += [_table(valid, "system")]
    else:
        parts.append("Not measured yet.\n")

    out = docs / "results.md"
    out.write_text("\n".join(parts), encoding="utf-8")
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
