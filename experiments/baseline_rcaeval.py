
from pathlib import Path
import argparse
import re
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "rcaeval"

# Longest suffixes first, to correctly handle latency-50 and latency-90.
METRIC_SUFFIXES = [
    "latency-50", "latency-90",
    "diskio", "workload", "socket",
    "latency", "error", "memory",
    "cpu", "mem", "load",
]

SUFFIX_PATTERN = re.compile(
    r"^(.+)_(" + "|".join(map(re.escape, METRIC_SUFFIXES)) + r")$"
)


def service_metric_columns(df):
    """Map service names to their numeric telemetry columns."""
    mapping = {}

    for col in df.columns:
        match = SUFFIX_PATTERN.match(str(col))
        if not match:
            continue

        service = match.group(1)
        if pd.api.types.is_numeric_dtype(df[col]):
            mapping.setdefault(service, []).append(col)

    return mapping


def anomaly_effect(reference, observed):
    """Robust, capped effect size for a change in a metric."""
    reference = np.asarray(reference, dtype=float)
    observed = np.asarray(observed, dtype=float)

    reference = reference[np.isfinite(reference)]
    observed = observed[np.isfinite(observed)]

    if len(reference) < 30 or len(observed) < 30:
        return None

    ref_median = np.median(reference)
    obs_median = np.median(observed)

    mad = np.median(np.abs(reference - ref_median))
    scale = 1.4826 * mad

    # Fallbacks for nearly constant reference metrics.
    if not np.isfinite(scale) or scale < 1e-12:
        scale = np.std(reference)

    if not np.isfinite(scale) or scale < 1e-12:
        scale = max(abs(ref_median) * 0.01, 1e-6)

    effect = abs(obs_median - ref_median) / scale
    return float(min(effect, 20.0))


def rank_case(row):
    case = str(row["case"])
    case_dir = DATA / case
    metrics_path = case_dir / "metrics.parquet"

    if not metrics_path.exists():
        return None, "metrics.parquet missing"

    try:
        df = pd.read_parquet(metrics_path)
    except Exception as exc:
        return None, f"could not read metrics: {exc}"

    required = {"time"}
    if not required.issubset(df.columns):
        return None, "time column missing"

    if "inject_time" not in row.index or pd.isna(row["inject_time"]):
        return None, "injection timestamp missing"

    df = df.sort_values("time")
    inject_time = float(row["inject_time"])

    # Only use telemetry before and at/after the injection timestamp.
    reference = df[df["time"] < inject_time]
    observed = df[df["time"] >= inject_time]

    if len(reference) < 30 or len(observed) < 30:
        return None, "insufficient pre/post-injection samples"

    mapping = service_metric_columns(df)
    scores = {}

    for service, columns in mapping.items():
        effects = []

        for col in columns:
            effect = anomaly_effect(
                reference[col].to_numpy(),
                observed[col].to_numpy(),
            )
            if effect is not None:
                effects.append(effect)

        if effects:
            # Average the strongest three changes so services with more
            # recorded metrics do not automatically dominate the ranking.
            strongest = sorted(effects, reverse=True)[:3]
            scores[service] = float(np.mean(strongest))

    if not scores:
        return None, "no usable service metrics"

    ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))

    truth = str(row.get("root_cause_service", "")).strip()
    result = {
        "case": case,
        "suite": str(row.get("suite", "")),
        "system": str(row.get("system_name", row.get("system", ""))),
        "fault": str(row.get("fault", "")),
        "root_cause": truth,
        "ranked_services": ranked,
        "ranked_names": [name for name, _ in ranked],
        "hit1": int(bool(truth) and ranked[0][0] == truth),
        "hit3": int(bool(truth) and truth in [s for s, _ in ranked[:3]]),
        "hit5": int(bool(truth) and truth in [s for s, _ in ranked[:5]]),
        "mrr": (
            1.0 / (next(
                (i for i, (service, _) in enumerate(ranked, start=1)
                 if service == truth),
                len(ranked) + 1
            ))
            if truth else 0.0
        ),
    }

    result["top3"] = ", ".join(
        f"{service} ({score:.2f})"
        for service, score in ranked[:3]
    )

    return result, None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--limit", type=int, default=20,
        help="Number of cases to test; use 0 for all cases."
    )
    args = parser.parse_args()

    index_path = DATA / "cases.parquet"
    if not index_path.exists():
        raise FileNotFoundError(f"Missing dataset index: {index_path}")

    index = pd.read_parquet(index_path)

    required = {"case", "root_cause_service", "inject_time"}
    missing = required - set(index.columns)
    if missing:
        raise ValueError(f"Dataset index is missing columns: {sorted(missing)}")

    # Test a reproducible sample first. Full evaluation comes after validation.
    cases = index.sort_values("case").reset_index(drop=True)
    if args.limit > 0:
        cases = cases.head(args.limit)

    results = []
    skipped = []

    print(f"RCAEval anomaly-only baseline")
    print(f"Cases selected: {len(cases)}")
    print(f"Mode: {'sample' if args.limit else 'full evaluation'}\n")

    for i, (_, row) in enumerate(cases.iterrows(), start=1):
        result, error = rank_case(row)

        if result is None:
            skipped.append({"case": row["case"], "reason": error})
        else:
            results.append(result)

        if i % 10 == 0 or i == len(cases):
            print(f"Processed {i}/{len(cases)} cases")

    output_dir = ROOT / "results"
    output_dir.mkdir(parents=True, exist_ok=True)

    detail_path = output_dir / "baseline_rcaeval.csv"
    skip_path = output_dir / "baseline_skipped.csv"

    if results:
        output = pd.DataFrame(results)
        output.drop(columns=["ranked_services", "ranked_names"]).to_csv(
            detail_path, index=False
        )

        print("\n" + "=" * 60)
        print("BASELINE RESULTS")
        print("=" * 60)
        print(f"Evaluated cases: {len(results)}")
        print(f"Skipped cases:   {len(skipped)}")
        print(f"Hit@1: {output['hit1'].mean():.4f}")
        print(f"Hit@3: {output['hit3'].mean():.4f}")
        print(f"Hit@5: {output['hit5'].mean():.4f}")
        print(f"MRR:    {output['mrr'].mean():.4f}")

        print("\nResults by suite:")
        print(
            output.groupby("suite")[["hit1", "hit3", "hit5", "mrr"]]
            .mean()
            .round(4)
            .to_string()
        )

        print(f"\nDetailed results saved to: {detail_path}")

        print("\nFirst 10 ranked predictions:")
        print(
            output[["case", "root_cause", "top3", "hit1"]]
            .head(10)
            .to_string(index=False)
        )
    else:
        print("No cases could be evaluated. Check the error report.")

    pd.DataFrame(skipped, columns=["case", "reason"]).to_csv(
        skip_path, index=False
    )
    print(f"Skipped-case report: {skip_path}")


if __name__ == "__main__":
    main()
