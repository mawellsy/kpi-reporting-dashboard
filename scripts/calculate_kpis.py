import json
from pathlib import Path
import sys

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
sys.path.insert(0, str(ROOT / "src"))

from kpi_dashboard.database import resolve_reporting_database_url
from kpi_dashboard.kpis import KPIEngine


if __name__ == "__main__":
    database_url = resolve_reporting_database_url(ROOT)
    snapshot = KPIEngine(database_url).latest_week()
    print(json.dumps(snapshot.to_dict(), indent=2))
