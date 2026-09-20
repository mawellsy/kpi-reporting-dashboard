import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from kpi_dashboard.kpis import KPIEngine


if __name__ == "__main__":
    reporting_db = ROOT / "data" / "processed" / "reporting.db"
    snapshot = KPIEngine(reporting_db).latest_week()
    print(json.dumps(snapshot.to_dict(), indent=2))
