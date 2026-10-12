
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "rcaeval"

index = pd.read_parquet(DATA / "cases.parquet")

TARGETS = [
    "re1ob_adservice_cpu_1",
    "re2ob_checkoutservice_cpu_1",
    "re2ss_carts_cpu_1",
    "re3ss_carts_f1_1",
]

TIME_COLUMNS = [
    "time", "timestamp", "inject_time",
    "time_start", "time_end",
    "normal_timesteps", "faulty_timesteps",
]

for case in TARGETS:
    matches = index[index["case"] == case]

    print("\n" + "=" * 75)
    print(f"CASE: {case}")

    if matches.empty:
        print("ERROR: Case not found in cases.parquet")
        continue

    row = matches.iloc[0]

    for column in [
        "suite", "system_name", "root_cause_service",
        "fault", "inject_time", "time_start", "time_end",
        "normal_timesteps", "faulty_timesteps",
    ]:
        if column in index.columns:
            value = row[column]
            print(f"{column}: {value!r} (type={type(value).__name__})")

    metrics_file = DATA / case / "metrics.parquet"

    if not metrics_file.exists():
        print("ERROR: metrics.parquet not found")
        continue

    metrics = pd.read_parquet(metrics_file)

    print(f"\nMetric shape: {metrics.shape}")
    print(f"Metric columns: {metrics.columns.tolist()}")

    for column in TIME_COLUMNS:
        if column in metrics.columns:
            series = metrics[column]
            print(
                f"{column}: dtype={series.dtype}, "
                f"first={series.iloc[0]!r}, "
                f"last={series.iloc[-1]!r}, "
                f"nulls={series.isna().sum()}"
            )

    print("\nFirst 2 metric rows:")
    print(metrics.head(2).to_string(index=False, max_cols=12))

print("\nTiming audit complete.")
