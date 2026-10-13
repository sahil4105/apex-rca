from pathlib import Path
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "openrca" / "processed" / "Bank"
CACHE_DIR = ROOT / "results" / "bank_metric_cache"
CHUNK_SIZE = 100_000

def main():
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    paths = sorted(DATA_DIR.glob("telemetry/*/metric/metric_container.csv"))
    if not paths:
        raise FileNotFoundError(f"No metric_container.csv files under {DATA_DIR}")

    for index, path in enumerate(paths, start=1):
        output = CACHE_DIR / f"{path.parent.parent.name}_container.parquet"
        if output.exists():
            raise FileExistsError(f"Refusing to overwrite existing cache: {output}")

        writer = None
        total_rows = 0
        try:
            for chunk in pd.read_csv(
                path,
                usecols=["timestamp", "cmdb_id", "kpi_name", "value"],
                chunksize=CHUNK_SIZE,
            ):
                chunk["timestamp"] = pd.to_numeric(chunk["timestamp"], errors="coerce")
                chunk["value"] = pd.to_numeric(chunk["value"], errors="coerce")
                chunk["cmdb_id"] = chunk["cmdb_id"].astype("string").str.strip()
                chunk["kpi_name"] = chunk["kpi_name"].astype("string").str.strip()
                chunk = chunk.dropna(
                    subset=["timestamp", "value", "cmdb_id", "kpi_name"]
                )
                if chunk.empty:
                    continue

                table = pa.Table.from_pandas(chunk, preserve_index=False)
                if writer is None:
                    writer = pq.ParquetWriter(output, table.schema, compression="snappy")
                writer.write_table(table)
                total_rows += len(chunk)
                del table, chunk

            if writer is None:
                print(f"[{index}/{len(paths)}] No valid rows: {path.name}")
            else:
                print(
                    f"[{index}/{len(paths)}] {path.parent.parent.name}: "
                    f"{total_rows:,} rows -> {output.name}"
                )
        except Exception:
            if writer is not None:
                writer.close()
            if output.exists():
                output.unlink()
            raise
        finally:
            if writer is not None:
                writer.close()

    print(f"Cache created at: {CACHE_DIR}")

if __name__ == "__main__":
    main()
