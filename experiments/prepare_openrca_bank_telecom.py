#!/usr/bin/env python
"""Prepare a compact, reproducible OpenRCA Bank/Telecom working dataset in processed_curated/.

Default: copy query/record indexes and metric CSVs only; audit files; preserve raw data.
Optional --cleanup-raw: after successful validation, asks for typed confirmation before
removing extracted raw folders. Original ZIP archives and processed outputs remain.
"""
from __future__ import annotations
import argparse, csv, hashlib, json, shutil, sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
try:
    import pandas as pd
except ImportError:
    raise SystemExit(r"pandas is required. Run: .\.venv\Scripts\python.exe -m pip install pandas")

ROOT = Path(__file__).resolve().parent.parent
OPENRCA = ROOT / "data" / "openrca"
RAW_ROOT = OPENRCA / "raw"
OUT_ROOT = OPENRCA / "processed_curated"
SYSTEMS = ("Bank", "Telecom")

def size_bytes(path: Path) -> int:
    try: return path.stat().st_size
    except OSError: return 0

def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()

def locate_system_root(system: str) -> Path:
    expected = RAW_ROOT / system / system
    if (expected / "query.csv").is_file() and (expected / "record.csv").is_file(): return expected
    matches = [p.parent for p in RAW_ROOT.glob(f"**/{system}/query.csv") if (p.parent / "record.csv").is_file()]
    if len(matches) == 1: return matches[0]
    if not matches: raise FileNotFoundError(f"Could not locate query.csv and record.csv for {system} under {RAW_ROOT}")
    raise RuntimeError(f"Multiple possible roots for {system}: {matches}; resolve layout manually")

def read_index(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str, keep_default_na=False, encoding_errors="replace")

def inspect_csv(path: Path) -> dict[str, Any]:
    info: dict[str, Any] = {"path": str(path), "name": path.name, "size_bytes": size_bytes(path),
        "size_mb": round(size_bytes(path)/(1024*1024), 3), "sha256": sha256_file(path)}
    try:
        with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as f:
            reader = csv.reader(f); header = next(reader, [])
        info["columns"] = header; info["column_count"] = len(header)
        # Stream rows without loading the full metric file into memory.
        with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as f:
            reader = csv.reader(f); next(reader, None); info["data_rows"] = sum(1 for _ in reader)
    except Exception as e: info["inspection_error"] = f"{type(e).__name__}: {e}"
    return info

def copy_verified(src: Path, dst: Path) -> dict[str, Any]:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if not dst.exists() or size_bytes(dst) != size_bytes(src): shutil.copy2(src, dst)
    source_hash, dest_hash = sha256_file(src), sha256_file(dst)
    if source_hash != dest_hash: raise IOError(f"SHA-256 verification failed: {src} -> {dst}")
    return {"source": str(src), "destination": str(dst), "size_bytes": size_bytes(dst), "sha256": dest_hash, "verified": True}

def process_system(system: str) -> dict[str, Any]:
    src_root = locate_system_root(system); out_root = OUT_ROOT / system; out_root.mkdir(parents=True, exist_ok=True)
    query_path, record_path = src_root / "query.csv", src_root / "record.csv"
    query, record = read_index(query_path), read_index(record_path)
    copies = [copy_verified(query_path, out_root / "query.csv"), copy_verified(record_path, out_root / "record.csv")]
    query_summary = {"rows": int(len(query)), "columns": list(query.columns), "sample_rows": query.head(3).to_dict(orient="records")}
    record_summary = {"rows": int(len(record)), "columns": list(record.columns), "sample_rows": record.head(3).to_dict(orient="records")}
    metric_sources = sorted(p for p in src_root.glob("telemetry/**/metric/*.csv") if p.is_file())
    metric_audit, metric_total = [], 0
    for src in metric_sources:
        rel = src.relative_to(src_root)
        # Retain the date and metric subfolder structure under processed/<system>/metrics.
        dst = out_root / "metrics" / rel.relative_to("telemetry")
        copied = copy_verified(src, dst); metric_total += size_bytes(src)
        audit = inspect_csv(src); audit["relative_path"] = str(rel); audit["processed_path"] = str(dst)
        audit["copy_verified"] = copied["verified"]; metric_audit.append(audit); copies.append(copied)
    # Keep indexes separate: do not join by row order unless a shared key is verified.
    rec_inv = record.copy(); rec_inv.insert(0, "record_row_number", range(1, len(rec_inv)+1)); rec_inv.insert(0, "dataset", system)
    rec_inv.to_csv(out_root / "record_inventory.csv", index=False)
    qry_inv = query.copy(); qry_inv.insert(0, "query_row_number", range(1, len(qry_inv)+1)); qry_inv.insert(0, "dataset", system)
    qry_inv.to_csv(out_root / "query_inventory.csv", index=False)
    return {"system": system, "source_root": str(src_root), "output_root": str(out_root),
        "query": query_summary, "record": record_summary, "query_record_row_count_match": len(query)==len(record),
        "metric_file_count": len(metric_sources), "metric_total_bytes": metric_total,
        "metric_total_gb": round(metric_total/(1024**3), 3), "metric_files": metric_audit,
        "copied_file_count": len(copies), "all_copies_verified": all(c["verified"] for c in copies),
        "logs_traces_copied": False,
        "note": "Indexes retained separately; no positional join assumed. Logs/traces were not copied and remain in raw extraction and ZIP archives."}

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cleanup-raw", action="store_true", help="After processing, request typed confirmation before deleting extracted raw Bank/Telecom folders. ZIPs remain.")
    args = parser.parse_args()
    for system in SYSTEMS:
        if not (RAW_ROOT / system).exists(): raise SystemExit(f"Expected extracted folder: {RAW_ROOT / system}")
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    report: dict[str, Any] = {"title": "OpenRCA Bank and Telecom preparation audit", "created_utc": datetime.now(timezone.utc).isoformat(),
        "project_root": str(ROOT), "raw_root": str(RAW_ROOT), "output_root": str(OUT_ROOT), "systems": {},
        "source_archives": {}, "cleanup_requested": bool(args.cleanup_raw), "cleanup_performed": False}
    for system in SYSTEMS:
        z = OPENRCA / f"{system}.zip"
        report["source_archives"][system] = {"path": str(z), "exists": z.is_file(), "size_bytes": size_bytes(z), "sha256": sha256_file(z) if z.is_file() else None}
    for system in SYSTEMS:
        print(f"\nProcessing {system} indexes and metrics...")
        item = process_system(system); report["systems"][system] = item
        print(f"  queries={item['query']['rows']}, records={item['record']['rows']}, metric CSVs={item['metric_file_count']}, metric size={item['metric_total_gb']} GB")
        if not item["query_record_row_count_match"]: print("  WARNING: query/record row counts differ; kept separate, not joined by row order")
        print(f"  copied files hash-verified: {item['all_copies_verified']}")
    for system in SYSTEMS:
        out = OUT_ROOT / system
        required = [out/"query.csv", out/"record.csv", out/"query_inventory.csv", out/"record_inventory.csv"]
        if not all(p.is_file() for p in required): raise RuntimeError(f"Required processed output missing for {system}")
        if not report["systems"][system]["all_copies_verified"]: raise RuntimeError(f"Copy verification failed for {system}")
    report_path = OUT_ROOT / "preparation_report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    flat = []
    for system, item in report["systems"].items():
        for m in item["metric_files"]:
            flat.append({"dataset": system, "relative_path": m.get("relative_path"), "processed_path": m.get("processed_path"),
                "size_mb": m.get("size_mb"), "data_rows": m.get("data_rows"), "columns": "|".join(m.get("columns", [])),
                "sha256": m.get("sha256"), "inspection_error": m.get("inspection_error", "")})
    inventory_path = OUT_ROOT / "metric_inventory.csv"; pd.DataFrame(flat).to_csv(inventory_path, index=False)
    print(f"\nPreparation report: {report_path}\nMetric inventory: {inventory_path}")
    print("Processed data contains indexes and metrics only. Raw logs/traces remain untouched. No files deleted.")
    if args.cleanup_raw:
        print("\nWARNING: this deletes extracted raw Bank and Telecom folders. ZIP archives and processed outputs remain.")
        if input("Type DELETE EXTRACTED RAW to continue: ").strip() != "DELETE EXTRACTED RAW":
            print("Cleanup cancelled; no raw files deleted."); return 0
        for system in SYSTEMS:
            raw = RAW_ROOT / system
            if raw.exists(): shutil.rmtree(raw); print(f"Deleted: {raw}")
        report["cleanup_performed"] = True; report["cleanup_completed_utc"] = datetime.now(timezone.utc).isoformat()
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print("Cleanup complete. ZIP archives and processed outputs were preserved.")
    return 0

if __name__ == "__main__": sys.exit(main())
