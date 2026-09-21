from __future__ import annotations

import json
import os
from pathlib import Path
import sys

import pandas as pd
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
sys.path.insert(0, str(ROOT / "src"))

from kpi_dashboard.anomalies import detect_anomalies
from kpi_dashboard.kpis import DateWindow, KPIEngine
from kpi_dashboard.management_summary import OpenAIResponsesProvider, generate_management_summary


REPORTING_DB = ROOT / "data" / "processed" / "reporting.db"


def main() -> None:
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY is required to generate the AI management summary")

    engine = KPIEngine(REPORTING_DB)
    frames = engine.load_frames()
    latest_date = pd.to_datetime(frames["sales"]["created_date"], errors="raise").max()
    window = DateWindow.ending_on(latest_date, days=7)
    snapshot = engine.snapshot(window)
    anomalies = detect_anomalies(frames, window, snapshot=snapshot)

    summary = generate_management_summary(
        snapshot,
        anomalies,
        OpenAIResponsesProvider(),
    )
    print(json.dumps(summary.to_dict(), indent=2))


if __name__ == "__main__":
    main()
