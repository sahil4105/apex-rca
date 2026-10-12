
from pathlib import Path
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "rcaeval"

index_file = DATA_DIR / "cases.parquet"

if not index_file.exists():
    raise FileNotFoundError(
        f"Case index not found: {index_file}"
    )

cases = pd.read_parquet(index_file)

print("Dataset index shape:", cases.shape)
print("\nAvailable columns:")
print(cases.columns.tolist())

if "dataset" in cases.columns:
    re1 = cases[
        cases["dataset"].astype(str).str.startswith("RE1")
    ]
else:
    re1 = cases

print("\nRE1 case count:", len(re1))
print("\nSample cases:")
print(re1.head(10).to_string(index=False))

print("\nDataset and fault distribution:")
for column in ("dataset", "fault"):
    if column in re1.columns:
        print(f"\n{column}:")
        print(re1[column].value_counts().to_string())
