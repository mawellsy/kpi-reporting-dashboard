import json
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from kpi_dashboard.data_generation import GenerationConfig, SyntheticDataGenerator
from kpi_dashboard.etl import ETLConfig, ETLPipeline
from kpi_dashboard.kpis import (
    DateWindow,
    KPIEngine,
    calculate_department_performance,
    calculate_operations_kpis,
    calculate_sales_kpis,
    calculate_support_kpis,
    filter_period,
    percentage_change,
)


def test_sales_kpis_calculate_revenue_growth_atv_and_conversion():
    current = pd.DataFrame(
        {
            "converted": [True, False, True, False],
            "revenue": [100.0, 0.0, 300.0, 0.0],
        }
    )
    previous = pd.DataFrame({"converted": [True, False], "revenue": [200.0, 0.0]})

    result = calculate_sales_kpis(current, previous)

    assert result.revenue == 400.0
    assert result.revenue_growth_pct == 100.0
    assert result.average_transaction_value == 200.0
    assert result.conversion_rate_pct == 50.0
    assert percentage_change(10, 0) is None


def test_support_kpis_calculate_resolution_unresolved_and_csat():
    support = pd.DataFrame(
        {
            "status": ["resolved", "resolved", "open"],
            "opened_at": [
                "2026-09-14T08:00:00+00:00",
                "2026-09-14T09:00:00+00:00",
                "2026-09-14T10:00:00+00:00",
            ],
            "resolved_at": [
                "2026-09-14T10:00:00+00:00",
                "2026-09-14T15:00:00+00:00",
                None,
            ],
            "satisfaction_score": [5, 3, None],
        }
    )

    result = calculate_support_kpis(support)

    assert result.ticket_volume == 3
    assert result.average_resolution_hours == 4.0
    assert result.unresolved_tickets == 1
    assert result.customer_satisfaction == 4.0


def test_operations_kpis_use_staffing_hours_for_productivity():
    operations = pd.DataFrame(
        {
            "status": ["completed", "completed", "open", "completed"],
            "delayed": [False, True, False, True],
        }
    )
    staffing = pd.DataFrame({"hours_worked": [100.0, 50.0]})

    result = calculate_operations_kpis(operations, staffing)

    assert result.jobs_completed == 3
    assert result.completion_rate_pct == 75.0
    assert result.delayed_jobs == 2
    assert result.productivity_jobs_per_100_hours == 2.0


def test_department_performance_calculates_target_gap_wow_and_rank():
    current = pd.DataFrame(
        {
            "department": ["A", "A", "B"],
            "revenue": [60.0, 60.0, 90.0],
        }
    )
    previous = pd.DataFrame(
        {
            "department": ["A", "B"],
            "revenue": [100.0, 100.0],
        }
    )

    result = calculate_department_performance(current, previous, {"A": 100.0, "B": 100.0})
    by_department = result.set_index("department")

    assert by_department.loc["A", "performance_vs_target_pct"] == 20.0
    assert by_department.loc["A", "week_over_week_pct"] == 20.0
    assert by_department.loc["A", "rank"] == 1
    assert by_department.loc["B", "performance_vs_target_pct"] == -10.0
    assert by_department.loc["B", "week_over_week_pct"] == -10.0
    assert by_department.loc["B", "rank"] == 2


def test_filter_period_is_inclusive_and_supports_org_filters():
    frame = pd.DataFrame(
        {
            "date": ["2026-09-13", "2026-09-14", "2026-09-20", "2026-09-21"],
            "department": ["A", "A", "B", "A"],
            "region": ["East", "East", "West", "East"],
        }
    )
    window = DateWindow.ending_on("2026-09-20", days=7)

    assert len(filter_period(frame, "date", window)) == 2
    assert len(filter_period(frame, "date", window, region="East")) == 1


def test_kpi_engine_builds_latest_week_snapshot_from_etl_database(tmp_path):
    raw_dir = tmp_path / "raw"
    reporting_db = tmp_path / "reporting.db"
    SyntheticDataGenerator(raw_dir, GenerationConfig(days=95, seed=7)).generate_all()
    ETLPipeline(ETLConfig(raw_dir=raw_dir, output_db=reporting_db)).run()

    snapshot = KPIEngine(reporting_db).latest_week()
    payload = snapshot.to_dict()

    assert payload["current_window"]["end"] == "2026-09-03"
    assert snapshot.sales.revenue > 0
    assert snapshot.sales.conversion_rate_pct is not None
    assert snapshot.support.ticket_volume > 0
    assert snapshot.operations.jobs_completed > 0
    assert len(snapshot.departments) == 4
    assert {row["rank"] for row in snapshot.departments} == {1, 2, 3, 4}
    json.dumps(payload)
