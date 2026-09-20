from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Mapping, Sequence

import pandas as pd

from .kpis import DateWindow, KPISnapshot, calculate_snapshot


@dataclass(frozen=True)
class AnomalyConfig:
    """Explicit deterministic thresholds used by the demo anomaly detector."""

    revenue_decline_threshold_pct: float = -10.0
    recent_average_windows: int = 4
    delayed_jobs_increase_threshold_pct: float = 30.0
    target_miss_critical_pct: float = -25.0

    def __post_init__(self) -> None:
        if self.recent_average_windows <= 0:
            raise ValueError("recent_average_windows must be positive")
        if self.delayed_jobs_increase_threshold_pct <= 0:
            raise ValueError("delayed_jobs_increase_threshold_pct must be positive")
        if self.target_miss_critical_pct >= 0:
            raise ValueError("target_miss_critical_pct must be negative")


@dataclass(frozen=True)
class Anomaly:
    category: str
    severity: str
    metric: str
    scope: str
    current_value: float
    reference_value: float | None
    deviation_pct: float | None
    message: str

    def to_dict(self) -> dict[str, str | float | None]:
        return asdict(self)


def _round(value: float | None, digits: int = 2) -> float | None:
    if value is None or pd.isna(value):
        return None
    return round(float(value), digits)


def _pct_change(current: float, baseline: float) -> float | None:
    if baseline == 0:
        return None
    return ((current - baseline) / baseline) * 100


def detect_threshold_changes(
    snapshot: KPISnapshot,
    config: AnomalyConfig = AnomalyConfig(),
) -> list[Anomaly]:
    """Flag direct KPI threshold breaches that require no historical model."""
    anomalies: list[Anomaly] = []
    growth = snapshot.sales.revenue_growth_pct
    if growth is not None and growth <= config.revenue_decline_threshold_pct:
        severity = "critical" if growth <= config.revenue_decline_threshold_pct * 2 else "warning"
        anomalies.append(
            Anomaly(
                category="threshold_change",
                severity=severity,
                metric="revenue_growth_pct",
                scope="Company",
                current_value=float(growth),
                reference_value=float(config.revenue_decline_threshold_pct),
                deviation_pct=None,
                message=(
                    f"Revenue changed {growth:+.2f}% versus the previous equal-length period, "
                    f"breaching the {config.revenue_decline_threshold_pct:.2f}% decline threshold."
                ),
            )
        )
    return anomalies


def detect_missed_targets(
    snapshot: KPISnapshot,
    config: AnomalyConfig = AnomalyConfig(),
) -> list[Anomaly]:
    """Flag departments below their scaled revenue target."""
    anomalies: list[Anomaly] = []
    for row in snapshot.departments:
        performance = row.get("performance_vs_target_pct")
        if performance is None or float(performance) >= 0:
            continue
        performance = float(performance)
        severity = "critical" if performance <= config.target_miss_critical_pct else "warning"
        anomalies.append(
            Anomaly(
                category="missed_target",
                severity=severity,
                metric="revenue_vs_target_pct",
                scope=str(row["department"]),
                current_value=float(row["revenue"]),
                reference_value=float(row["target_revenue"]),
                deviation_pct=_round(performance),
                message=(
                    f"{row['department']} revenue is {abs(performance):.2f}% below its "
                    "scaled target for the selected period."
                ),
            )
        )
    return anomalies


def detect_recent_average_deviations(
    snapshot: KPISnapshot,
    history: Sequence[KPISnapshot],
    config: AnomalyConfig = AnomalyConfig(),
) -> list[Anomaly]:
    """Compare selected metrics with the mean of recent equal-length periods."""
    if not history:
        return []

    previous_delays = [float(item.operations.delayed_jobs) for item in history]
    baseline_delays = sum(previous_delays) / len(previous_delays)
    current_delays = float(snapshot.operations.delayed_jobs)
    deviation = _pct_change(current_delays, baseline_delays)

    if deviation is None or deviation < config.delayed_jobs_increase_threshold_pct:
        return []

    severity = "critical" if deviation >= config.delayed_jobs_increase_threshold_pct * 2 else "warning"
    return [
        Anomaly(
            category="recent_average",
            severity=severity,
            metric="delayed_jobs",
            scope="Company",
            current_value=current_delays,
            reference_value=_round(baseline_delays),
            deviation_pct=_round(deviation),
            message=(
                f"Delayed jobs are {deviation:.2f}% above the average of the previous "
                f"{len(history)} equal-length periods."
            ),
        )
    ]


def _recent_history(
    frames: Mapping[str, pd.DataFrame],
    window: DateWindow,
    *,
    department: str | None,
    region: str | None,
    count: int,
) -> list[KPISnapshot]:
    sales_dates = pd.to_datetime(frames["sales"]["created_date"], errors="coerce").dropna().dt.normalize()
    if sales_dates.empty:
        return []
    minimum_date = sales_dates.min()

    history: list[KPISnapshot] = []
    cursor_end = window.start - pd.Timedelta(days=1)
    for _ in range(count):
        candidate = DateWindow.ending_on(cursor_end, days=window.days)
        if candidate.start < minimum_date:
            break
        history.append(
            calculate_snapshot(
                frames,
                candidate,
                department=department,
                region=region,
            )
        )
        cursor_end = candidate.start - pd.Timedelta(days=1)
    return history


def detect_anomalies(
    frames: Mapping[str, pd.DataFrame],
    window: DateWindow,
    *,
    department: str | None = None,
    region: str | None = None,
    config: AnomalyConfig = AnomalyConfig(),
    snapshot: KPISnapshot | None = None,
) -> list[Anomaly]:
    """Run the deterministic anomaly rules for one reporting window."""
    current = snapshot or calculate_snapshot(frames, window, department=department, region=region)
    history = _recent_history(
        frames,
        window,
        department=department,
        region=region,
        count=config.recent_average_windows,
    )

    anomalies = [
        *detect_threshold_changes(current, config),
        *detect_recent_average_deviations(current, history, config),
        *detect_missed_targets(current, config),
    ]
    severity_order = {"critical": 0, "warning": 1}
    return sorted(
        anomalies,
        key=lambda item: (severity_order.get(item.severity, 9), item.category, item.scope, item.metric),
    )
