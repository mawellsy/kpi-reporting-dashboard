from __future__ import annotations

import json
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from kpi_dashboard.anomalies import detect_anomalies
from kpi_dashboard.kpis import DateWindow, KPIEngine


REPORTING_DB = ROOT / "data" / "processed" / "reporting.db"


def main() -> None:
    engine = KPIEngine(REPORTING_DB)
    frames = engine.load_frames()
    latest_date = pd.to_datetime(frames["sales"]["created_date"], errors="raise").max()
    window = DateWindow.ending_on(latest_date, days=7)
    anomalies = detect_anomalies(frames, window)
    print(json.dumps([item.to_dict() for item in anomalies], indent=2))


if __name__ == "__main__":
    main()
