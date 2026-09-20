from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from kpi_dashboard.anomalies import AnomalyConfig, detect_anomalies
from kpi_dashboard.dashboard import build_dashboard_data
from kpi_dashboard.kpis import DateWindow, KPIEngine


REPORTING_DB = ROOT / "data" / "processed" / "reporting.db"


def latest_week():
    frames = KPIEngine(REPORTING_DB).load_frames()
    return frames, DateWindow(pd.Timestamp("2026-09-14"), pd.Timestamp("2026-09-20"))


def test_latest_week_exercises_all_three_anomaly_rule_types():
    frames, window = latest_week()

    anomalies = detect_anomalies(frames, window)

    assert {item.category for item in anomalies} == {
        "threshold_change",
        "recent_average",
        "missed_target",
    }
    assert any(item.metric == "revenue_growth_pct" and item.current_value == -10.62 for item in anomalies)
    assert any(item.metric == "delayed_jobs" and item.deviation_pct is not None for item in anomalies)
    assert {item.scope for item in anomalies if item.category == "missed_target"} == {"Southeast", "Southwest"}


def test_recent_average_rule_uses_previous_equal_length_windows_only():
    frames, window = latest_week()

    anomaly = next(item for item in detect_anomalies(frames, window) if item.metric == "delayed_jobs")

    assert anomaly.reference_value == 28.25
    assert anomaly.current_value == 39.0
    assert anomaly.deviation_pct == 38.05


def test_early_window_skips_recent_average_when_history_is_unavailable():
    frames = KPIEngine(REPORTING_DB).load_frames()
    window = DateWindow(pd.Timestamp("2026-06-01"), pd.Timestamp("2026-06-07"))

    anomalies = detect_anomalies(frames, window)

    assert all(item.category != "recent_average" for item in anomalies)


def test_department_filter_limits_target_anomalies_to_selected_department():
    frames, window = latest_week()

    anomalies = detect_anomalies(frames, window, department="Southwest")

    target_anomalies = [item for item in anomalies if item.category == "missed_target"]
    assert len(target_anomalies) == 1
    assert target_anomalies[0].scope == "Southwest"


def test_configuration_rejects_invalid_recent_window_count():
    try:
        AnomalyConfig(recent_average_windows=0)
    except ValueError as exc:
        assert "recent_average_windows" in str(exc)
    else:
        raise AssertionError("expected invalid configuration to raise ValueError")


def test_dashboard_data_exposes_anomalies_from_same_filter_context():
    frames, window = latest_week()

    data = build_dashboard_data(frames, window, department="Southwest")

    assert data.anomalies
    assert all(item.scope in {"Company", "Southwest"} for item in data.anomalies)
