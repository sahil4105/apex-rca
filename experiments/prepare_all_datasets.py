
from pathlib import Path, PurePosixPath
from zipfile import ZipFile
import csv
import json
import shutil
import sys

PROJECT = Path(__file__).resolve().parent.parent
RCA_INDEX = PROJECT / "data" / "rcaeval" / "cases.parquet"
OPENRCA_DIR = PROJECT / "data" / "openrca"
OUTPUT_DIR = OPENRCA_DIR / "processed"
REPORT_PATH = OUTPUT_DIR / "preparation_report.json"

SYSTEMS = ("Bank", "Telecom")
MAX_EXTRACT_GB = 8.0


def inspect_rcaeval():
    print("\n" + "=" * 65)
    print("1. RCAEval primary benchmark")
    print("=" * 65)

    if not RCA_INDEX.exists():
        print(f"ERROR: Missing case index: {RCA_INDEX}")
        print("Check the existing data/rcaeval directory before continuing.")
        return {}

    try:
        import pandas as pd
        df = pd.read_parquet(RCA_INDEX)
        summary = {
            "case_count": int(len(df)),
            "systems": {
                str(k): int(v)
                for k, v in df["system_name"].value_counts().items()
            },
            "suites": {
                str(k): int(v)
                for k, v in df["suite"].value_counts().items()
            },
            "fault_types": int(df["fault"].nunique()),
            "cases_with_logs": int(df["has_logs"].sum()),
            "cases_with_traces": int(df["has_traces"].sum()),
        }
        print(json.dumps(summary, indent=2))
        return summary
    except Exception as exc:
        print(f"Could not read RCAEval index: {exc}")
        return {}


def selected_entries(zip_file, system):
    """Select indexes and metric CSVs, excluding logs and traces."""
    selected = []

    for info in zip_file.infolist():
        if info.is_dir():
            continue

        path = PurePosixPath(info.filename)
        if not path.parts or path.parts[0] != system:
            continue

        relative = PurePosixPath(*path.parts[1:])
        relative_text = relative.as_posix()

        is_index = relative_text in ("query.csv", "record.csv")
        is_metric = (
            "metric" in relative.parts
            and relative.suffix.lower() == ".csv"
            and path.name != ".DS_Store"
        )

        if is_index or is_metric:
            selected.append((info, relative))

    return selected


def extract_selected(zip_path, system, entries, destination_root):
    system_root = destination_root / system
    total = len(entries)

    for number, (info, relative) in enumerate(entries, start=1):
        destination = system_root.joinpath(*relative.parts)

        # Defend against unexpected archive paths.
        if not destination.resolve().is_relative_to(
            system_root.resolve()
        ):
            raise ValueError(f"Unsafe archive path: {info.filename}")

        destination.parent.mkdir(parents=True, exist_ok=True)

        with ZipFile(zip_path) as zf:
            with zf.open(info) as source, destination.open("wb") as target:
                shutil.copyfileobj(source, target, length=1024 * 1024)

        if number % 10 == 0 or number == total:
            print(f"  {system}: extracted {number}/{total} selected files")

    return total


def inspect_csv(path, count_rows=False):
    result = {"path": str(path), "size_mb": round(path.stat().st_size / 1e6, 2)}

    with path.open("r", encoding="utf-8-sig", newline="", errors="replace") as f:
        reader = csv.reader(f)
        result["columns"] = next(reader, [])
        if count_rows:
            result["data_rows"] = sum(1 for _ in reader)
        else:
            result["sample_rows"] = [row for _, row in zip(range(2), reader)]

    return result


def main():
    print("APEX-RCA: consolidated dataset preparation")
    print(f"Project: {PROJECT}")
    print(f"Output:  {OUTPUT_DIR}")

    rca_summary = inspect_rcaeval()

    if not OUTPUT_DIR.exists():
        OUTPUT_DIR.mkdir(parents=True)

    plans = {}
    total_bytes = 0

    print("\n" + "=" * 65)
    print("2. Preflight Microsoft OpenRCA archives")
    print("=" * 65)

    for system in SYSTEMS:
        zip_path = OPENRCA_DIR / f"{system}.zip"

        if not zip_path.exists():
            raise FileNotFoundError(
                f"Missing {zip_path}. Keep the original ZIPs in {OPENRCA_DIR}"
            )

        with ZipFile(zip_path) as zf:
            entries = selected_entries(zf, system)
            plans[system] = entries
            selected_bytes = sum(info.file_size for info, _ in entries)
            total_bytes += selected_bytes

            metric_count = sum(
                1 for _, relative in entries if "metric" in relative.parts
            )

            print(
                f"{system}: {len(entries)} selected files; "
                f"{metric_count} metric CSVs; "
                f"{selected_bytes / 1e9:.2f} GB uncompressed"
            )

    print(f"Total selected extraction: {total_bytes / 1e9:.2f} GB")

    if total_bytes > MAX_EXTRACT_GB * 1e9:
        raise RuntimeError(
            f"Safety limit of {MAX_EXTRACT_GB} GB exceeded. "
            "Nothing was extracted. Review the file selection first."
        )

    print("\n" + "=" * 65)
    print("3. Extract indexes and all daily metric CSVs")
    print("Logs and traces are intentionally excluded.")
    print("=" * 65)

    extracted = {}
    for system in SYSTEMS:
        extracted[system] = extract_selected(
            OPENRCA_DIR / f"{system}.zip",
            system,
            plans[system],
            OUTPUT_DIR,
        )

    print("\n" + "=" * 65)
    print("4. Validate extracted indexes and metric schemas")
    print("=" * 65)

    report = {
        "rcaeval": rca_summary,
        "openrca": {},
        "scope": (
            "Bank and Telecom query/record indexes plus all daily metric "
            "CSVs. Logs and traces excluded from this preparation run."
        ),
    }

    for system in SYSTEMS:
        system_root = OUTPUT_DIR / system
        system_report = {
            "selected_files_extracted": extracted[system],
            "metric_files": [],
        }

        for index_name in ("query.csv", "record.csv"):
            path = system_root / index_name
            if not path.exists():
                raise FileNotFoundError(f"Expected index not found: {path}")

            index_report = inspect_csv(path, count_rows=True)
            system_report[index_name] = index_report
            print(f"\n{system}/{index_name}")
            print(f"  Rows: {index_report['data_rows']}")
            print(f"  Columns: {index_report['columns']}")

        metric_paths = sorted(
            p for p in (system_root / "telemetry").rglob("*.csv")
            if "metric" in p.parts
        )

        for path in metric_paths:
            info = inspect_csv(path)
            system_report["metric_files"].append(info)

        system_report["metric_file_count"] = len(metric_paths)
        system_report["metric_total_mb"] = round(
            sum(p.stat().st_size for p in metric_paths) / 1e6, 2
        )

        print(f"\n{system} metric CSVs: {len(metric_paths)}")
        print(f"Combined metric size: {system_report['metric_total_mb']} MB")

        for item in system_report["metric_files"][:3]:
            print(f"  Sample: {item['path']}")
            print(f"  Columns: {item['columns'][:12]}")

        report["openrca"][system] = system_report

    REPORT_PATH.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("\n" + "=" * 65)
    print("PREPARATION COMPLETE")
    print(f"Report: {REPORT_PATH}")
    print(f"Processed data: {OUTPUT_DIR}")
    print("Original ZIP archives have been preserved.")
    print("=" * 65)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"\nPREPARATION STOPPED: {exc}")
        sys.exit(1)
