from __future__ import annotations

import json
from pathlib import Path
import sys

import pandas as pd
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
sys.path.insert(0, str(ROOT / "src"))

from kpi_dashboard.anomalies import detect_anomalies
from kpi_dashboard.database import resolve_reporting_database_url
from kpi_dashboard.kpis import DateWindow, KPIEngine


def main() -> None:
    database_url = resolve_reporting_database_url(ROOT)
    engine = KPIEngine(database_url)
    frames = engine.load_frames()
    latest_date = pd.to_datetime(frames["sales"]["created_date"], errors="raise").max()
    window = DateWindow.ending_on(latest_date, days=7)
    anomalies = detect_anomalies(frames, window)
    print(json.dumps([item.to_dict() for item in anomalies], indent=2))


if __name__ == "__main__":
    main()
