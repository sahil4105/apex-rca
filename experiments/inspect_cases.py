
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "rcaeval"

index = pd.read_parquet(DATA / "cases.parquet")

targets = [
    "re1ob_adservice_cpu_1",
    "re2ob_checkoutservice_cpu_1",
    "re2ss_carts_cpu_1",
    "re3ss_carts_f1_1",
]

for case in targets:
    matches = index[index["case"] == case]

    if matches.empty:
        print(f"\n{'=' * 65}\nCASE NOT FOUND: {case}")
        continue

    row = matches.iloc[0]
    folder = DATA / case

    print(f"\n{'=' * 65}")
    print(f"CASE: {case}")
    print("\nGround-truth and timing metadata:")

    for col in [
        "suite", "system", "system_name",
        "root_cause_service", "fault",
        "fault_description", "inject_time",
        "time_start", "time_end",
        "normal_timesteps", "faulty_timesteps",
        "has_logs", "has_traces",
        "has_root_cause_file",
    ]:
        if col in index.columns:
            print(f"  {col}: {row[col]}")

    print("\nFiles in incident directory:")
    if folder.exists():
        for file in sorted(folder.iterdir()):
            print(f"  {file.name} ({file.stat().st_size:,} bytes)")

    for filename in [
        "metrics.parquet",
        "logs.parquet",
        "traces.parquet",
    ]:
        file = folder / filename

        if not file.exists():
            continue

        try:
            df = pd.read_parquet(file)
            print(f"\n{filename}: shape={df.shape}")
            print("  Columns:", df.columns.tolist()[:25])
            print("  Dtypes:")
            print(df.dtypes.head(12).to_string())
            print("  First 3 rows:")
            print(df.head(3).to_string(index=False, max_cols=8))
        except Exception as exc:
            print(f"  ERROR reading {filename}: {exc}")
