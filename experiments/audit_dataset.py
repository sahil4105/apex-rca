
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "rcaeval"
INDEX = DATA / "cases.parquet"

if not INDEX.exists():
    raise FileNotFoundError(f"Dataset index not found: {INDEX}")

df = pd.read_parquet(INDEX)

print("=" * 65)
print("APEX-RCA | RCAEval Dataset Audit")
print("=" * 65)

print(f"\nIndexed cases: {len(df)}")
print(f"Index columns: {len(df.columns)}")

required = {
    "case", "suite", "system",
    "root_cause_service", "fault",
    "has_logs", "has_traces",
    "has_root_cause_file",
}

missing_columns = required - set(df.columns)
print(f"Required columns missing: {sorted(missing_columns)}")

print("\n--- Cases by suite and system ---")
print(df.groupby(["suite", "system"]).size().to_string())

print("\n--- Label completeness ---")
for col in ["case", "suite", "system", "root_cause_service", "fault"]:
    if col in df.columns:
        missing = int(df[col].isna().sum())
        print(f"{col}: {len(df) - missing}/{len(df)} populated")

print("\n--- Telemetry availability ---")
for col in ["has_logs", "has_traces", "has_root_cause_file"]:
    if col in df.columns:
        print(f"{col}: {int(df[col].fillna(False).astype(bool).sum())}")

print("\n--- Physical file audit ---")
folder_count = 0
missing_metrics = []
missing_logs = []
missing_traces = []
missing_root_cause = []

for _, row in df.iterrows():
    case = str(row["case"])
    folder = DATA / case

    if folder.is_dir():
        folder_count += 1

    if not folder.is_dir() or not (folder / "metrics.parquet").exists():
        missing_metrics.append(case)

    if bool(row.get("has_logs", False)):
        if not (folder / "logs.parquet").exists():
            missing_logs.append(case)

    if bool(row.get("has_traces", False)):
        if not (folder / "traces.parquet").exists():
            missing_traces.append(case)

    if bool(row.get("has_root_cause_file", False)):
        if not (folder / "root_cause.json").exists():
            # Record for inspection; filenames may vary by suite.
            missing_root_cause.append(case)

print(f"Case folders found: {folder_count}/{len(df)}")
print(f"Missing metrics files: {len(missing_metrics)}")
print(f"Missing advertised logs files: {len(missing_logs)}")
print(f"Missing advertised traces files: {len(missing_traces)}")
print(f"Root-cause files needing filename inspection: {len(missing_root_cause)}")

if missing_metrics:
    print("Examples missing metrics:", missing_metrics[:10])
if missing_logs:
    print("Examples missing logs:", missing_logs[:10])
if missing_traces:
    print("Examples missing traces:", missing_traces[:10])
if missing_root_cause:
    print("Examples to inspect:", missing_root_cause[:10])

print("\n--- Sample telemetry schemas ---")
sample_cases = df.head(3)["case"].astype(str).tolist()

for case in sample_cases:
    folder = DATA / case
    print(f"\n{case}")

    for filename in [
        "metrics.parquet",
        "logs.parquet",
        "traces.parquet",
    ]:
        file = folder / filename

        if file.exists():
            try:
                sample = pd.read_parquet(file)
                print(
                    f"  {filename}: "
                    f"shape={sample.shape}, "
                    f"columns={sample.columns.tolist()}"
                )
            except Exception as exc:
                print(f"  {filename}: READ ERROR: {exc}")

print("\nAudit finished.")
