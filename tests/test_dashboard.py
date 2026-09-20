from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from kpi_dashboard.dashboard import build_dashboard_data, get_filter_options
from kpi_dashboard.kpis import DateWindow, KPIEngine, calculate_snapshot, scaled_revenue_targets


REPORTING_DB = ROOT / "data" / "processed" / "reporting.db"


def test_filter_options_come_from_reporting_dimensions():
    frames = KPIEngine(REPORTING_DB).load_frames()
    options = get_filter_options(frames)

    assert options.minimum_date == pd.Timestamp("2026-06-01")
    assert options.maximum_date == pd.Timestamp("2026-09-20")
    assert options.departments == ("Northeast", "Northwest", "Southeast", "Southwest")
    assert options.regions == ("East", "West")


def test_custom_snapshot_filters_region_and_uses_equal_comparison_period():
    frames = KPIEngine(REPORTING_DB).load_frames()
    window = DateWindow(pd.Timestamp("2026-09-14"), pd.Timestamp("2026-09-20"))

    snapshot = calculate_snapshot(frames, window, region="West")

    assert snapshot.current_window.days == 7
    assert snapshot.previous_window == DateWindow(pd.Timestamp("2026-09-07"), pd.Timestamp("2026-09-13"))
    assert {row["department"] for row in snapshot.departments} == {"Northwest", "Southwest"}
    assert snapshot.sales.revenue > 0


def test_targets_scale_to_selected_window_length():
    targets = scaled_revenue_targets(14, ["Northeast", "Southwest"])

    assert targets["Northeast"] == 150_000.0
    assert targets["Southwest"] == 120_000.0


def test_dashboard_data_builds_chart_ready_daily_series():
    frames = KPIEngine(REPORTING_DB).load_frames()
    window = DateWindow(pd.Timestamp("2026-09-14"), pd.Timestamp("2026-09-20"))

    data = build_dashboard_data(frames, window, department="Southwest")

    assert len(data.sales_trend) == 7
    assert len(data.support_trend) == 7
    assert len(data.operations_trend) == 7
    assert list(data.department_performance["department"]) == ["Southwest"]
    assert {"revenue", "opportunities", "conversions", "conversion_rate_pct"}.issubset(data.sales_trend.columns)
    assert {"ticket_volume", "unresolved_tickets", "customer_satisfaction"}.issubset(data.support_trend.columns)
    assert {"jobs_completed", "delayed_jobs", "completion_rate_pct"}.issubset(data.operations_trend.columns)
