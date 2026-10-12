
from pathlib import Path
from huggingface_hub import snapshot_download

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "rcaeval"

DATA_DIR.mkdir(parents=True, exist_ok=True)

print("Downloading the complete RCAEval benchmark (735 cases)...")
print("This may take some time.")

snapshot_download(
    repo_id="phamquiluan/RCAEval",
    repo_type="dataset",
    allow_patterns=[
        "cases.parquet",
        "re1*",
        "re2*",
        "re3*",
    ],
    local_dir=str(DATA_DIR),
)

print(f"\nDownload completed: {DATA_DIR}")
