from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from kpi_dashboard.etl import ETLConfig, ETLPipeline


if __name__ == "__main__":
    raw_dir = ROOT / "data" / "raw"
    output_db = ROOT / "data" / "processed" / "reporting.db"
    result = ETLPipeline(ETLConfig(raw_dir=raw_dir, output_db=output_db)).run()

    print(f"ETL run: {result.run_id}")
    for source in result.extracted_rows:
        print(
            f"{source:10} extracted={result.extracted_rows[source]:5d} "
            f"loaded={result.loaded_rows[source]:5d} "
            f"rejected={result.rejected_rows[source]:3d}"
        )
    print(f"Reporting database: {output_db}")
