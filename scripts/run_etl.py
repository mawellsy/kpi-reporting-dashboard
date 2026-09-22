from pathlib import Path
import sys

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
sys.path.insert(0, str(ROOT / "src"))

from kpi_dashboard.database import database_display_name, resolve_reporting_database_url
from kpi_dashboard.etl import ETLConfig, ETLPipeline


if __name__ == "__main__":
    raw_dir = ROOT / "data" / "raw"
    database_url = resolve_reporting_database_url(ROOT)
    result = ETLPipeline(ETLConfig(raw_dir=raw_dir, database_url=database_url)).run()

    print(f"ETL run: {result.run_id}")
    for source in result.extracted_rows:
        print(
            f"{source:10} extracted={result.extracted_rows[source]:5d} "
            f"loaded={result.loaded_rows[source]:5d} "
            f"rejected={result.rejected_rows[source]:3d}"
        )
    print(f"Reporting database: {database_display_name(database_url)}")
