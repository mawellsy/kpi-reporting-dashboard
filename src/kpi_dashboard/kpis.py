from __future__ import annotations

import sqlite3
from dataclasses import asdict, dataclass
from datetime import timedelta
from pathlib import Path
from typing import Mapping

import pandas as pd


DEFAULT_WEEKLY_REVENUE_TARGETS: dict[str, float] = {
    "Northeast": 75_000.0,
    "Southeast": 70_000.0,
    "Northwest": 65_000.0,
    "Southwest": 60_000.0,
}


@dataclass(frozen=True)
class DateWindow:
    start: pd.Timestamp
    end: pd.Timestamp

    def __post_init__(self) -> None:
        start = pd.Timestamp(self.start).normalize()
        end = pd.Timestamp(self.end).normalize()
        if end < start:
            raise ValueError("end date cannot precede start date")
        object.__setattr__(self, "start", start)
        object.__setattr__(self, "end", end)

    @classmethod
    def ending_on(cls, end: str | pd.Timestamp, days: int = 7) -> "DateWindow":
        if days <= 0:
            raise ValueError("days must be positive")
        end_ts = pd.Timestamp(end).normalize()
        return cls(start=end_ts - timedelta(days=int(days) - 1), end=end_ts)

    @property
    def days(self) -> int:
        return (self.end - self.start).days + 1

    def previous(self) -> "DateWindow":
        previous_end = self.start - timedelta(days=1)
        return DateWindow.ending_on(previous_end, days=self.days)


@dataclass(frozen=True)
class SalesKPIs:
    revenue: float
    revenue_growth_pct: float | None
    average_transaction_value: float | None
    conversion_rate_pct: float | None


@dataclass(frozen=True)
class SupportKPIs:
    ticket_volume: int
    average_resolution_hours: float | None
    unresolved_tickets: int
    customer_satisfaction: float | None


@dataclass(frozen=True)
class OperationsKPIs:
    jobs_completed: int
    completion_rate_pct: float | None
    delayed_jobs: int
    productivity_jobs_per_100_hours: float | None


@dataclass(frozen=True)
class KPISnapshot:
    current_window: DateWindow
    previous_window: DateWindow
    sales: SalesKPIs
    support: SupportKPIs
    operations: OperationsKPIs
    departments: list[dict[str, float | int | str | None]]

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["current_window"] = {
            "start": self.current_window.start.date().isoformat(),
            "end": self.current_window.end.date().isoformat(),
        }
        payload["previous_window"] = {
            "start": self.previous_window.start.date().isoformat(),
            "end": self.previous_window.end.date().isoformat(),
        }
        return payload


def _round(value: float | None, digits: int = 2) -> float | None:
    if value is None or pd.isna(value):
        return None
    return round(float(value), digits)


def percentage_change(current: float, previous: float) -> float | None:
    """Return percentage change, or None when the prior value is zero."""
    if previous == 0:
        return None
    return ((current - previous) / previous) * 100


def filter_scope(
    frame: pd.DataFrame,
    *,
    department: str | None = None,
    region: str | None = None,
) -> pd.DataFrame:
    """Apply optional department/region filters without changing the source frame."""
    mask = pd.Series(True, index=frame.index)
    if department is not None:
        mask &= frame["department"].eq(department)
    if region is not None:
        mask &= frame["region"].eq(region)
    return frame.loc[mask].copy().reset_index(drop=True)


def filter_period(
    frame: pd.DataFrame,
    date_column: str,
    window: DateWindow,
    *,
    department: str | None = None,
    region: str | None = None,
) -> pd.DataFrame:
    """Return records inside an inclusive date window and optional org filters."""
    if date_column not in frame.columns:
        raise ValueError(f"missing date column: {date_column}")

    scoped = filter_scope(frame, department=department, region=region)
    dates = pd.to_datetime(scoped[date_column], errors="coerce", utc=True).dt.tz_localize(None).dt.normalize()
    mask = dates.between(window.start, window.end, inclusive="both")
    return scoped.loc[mask].copy().reset_index(drop=True)


def calculate_sales_kpis(
    current_sales: pd.DataFrame,
    previous_sales: pd.DataFrame | None = None,
) -> SalesKPIs:
    revenue = float(pd.to_numeric(current_sales["revenue"], errors="coerce").fillna(0).sum())
    converted = current_sales["converted"].fillna(False).astype(bool)
    opportunity_count = len(current_sales)
    conversion_rate = None if opportunity_count == 0 else converted.mean() * 100

    converted_revenue = pd.to_numeric(current_sales.loc[converted, "revenue"], errors="coerce").dropna()
    average_transaction_value = None if converted_revenue.empty else float(converted_revenue.mean())

    growth = None
    if previous_sales is not None:
        previous_revenue = float(pd.to_numeric(previous_sales["revenue"], errors="coerce").fillna(0).sum())
        growth = percentage_change(revenue, previous_revenue)

    return SalesKPIs(
        revenue=round(revenue, 2),
        revenue_growth_pct=_round(growth),
        average_transaction_value=_round(average_transaction_value),
        conversion_rate_pct=_round(conversion_rate),
    )


def calculate_support_kpis(support: pd.DataFrame) -> SupportKPIs:
    ticket_volume = len(support)
    status = support["status"].astype(str)
    unresolved = int(status.ne("resolved").sum())

    opened = pd.to_datetime(support["opened_at"], errors="coerce", utc=True)
    resolved = pd.to_datetime(support["resolved_at"], errors="coerce", utc=True)
    valid_resolution = opened.notna() & resolved.notna() & status.eq("resolved")
    resolution_hours = (resolved[valid_resolution] - opened[valid_resolution]).dt.total_seconds() / 3600
    average_resolution = None if resolution_hours.empty else float(resolution_hours.mean())

    satisfaction = pd.to_numeric(support["satisfaction_score"], errors="coerce").dropna()
    customer_satisfaction = None if satisfaction.empty else float(satisfaction.mean())

    return SupportKPIs(
        ticket_volume=ticket_volume,
        average_resolution_hours=_round(average_resolution),
        unresolved_tickets=unresolved,
        customer_satisfaction=_round(customer_satisfaction),
    )


def calculate_operations_kpis(
    operations: pd.DataFrame,
    staffing: pd.DataFrame,
) -> OperationsKPIs:
    completed = operations["status"].astype(str).eq("completed")
    total_jobs = len(operations)
    completion_rate = None if total_jobs == 0 else completed.mean() * 100

    delayed = operations["delayed"].fillna(False).astype(bool)
    delayed_jobs = int(delayed.sum())

    staffing_hours = float(pd.to_numeric(staffing["hours_worked"], errors="coerce").fillna(0).sum())
    productivity = None if staffing_hours <= 0 else (int(completed.sum()) / staffing_hours) * 100

    return OperationsKPIs(
        jobs_completed=int(completed.sum()),
        completion_rate_pct=_round(completion_rate),
        delayed_jobs=delayed_jobs,
        productivity_jobs_per_100_hours=_round(productivity),
    )


def calculate_department_performance(
    current_sales: pd.DataFrame,
    previous_sales: pd.DataFrame,
    revenue_targets: Mapping[str, float] = DEFAULT_WEEKLY_REVENUE_TARGETS,
) -> pd.DataFrame:
    """Compare departments on revenue vs target and period-over-period revenue change."""
    current = current_sales.groupby("department", as_index=False)["revenue"].sum()
    previous = previous_sales.groupby("department", as_index=False)["revenue"].sum()
    previous = previous.rename(columns={"revenue": "previous_revenue"})

    departments = sorted(set(revenue_targets) | set(current["department"]) | set(previous["department"]))
    result = pd.DataFrame({"department": departments})
    result = result.merge(current, on="department", how="left")
    result = result.merge(previous, on="department", how="left")
    result[["revenue", "previous_revenue"]] = result[["revenue", "previous_revenue"]].fillna(0.0)
    result["target_revenue"] = result["department"].map(revenue_targets)

    if result["target_revenue"].isna().any():
        missing = result.loc[result["target_revenue"].isna(), "department"].tolist()
        raise ValueError(f"missing revenue target for department(s): {', '.join(missing)}")

    result["performance_vs_target_pct"] = (
        (result["revenue"] - result["target_revenue"]) / result["target_revenue"] * 100
    )
    result["week_over_week_pct"] = result.apply(
        lambda row: percentage_change(float(row["revenue"]), float(row["previous_revenue"])),
        axis=1,
    )
    result["rank"] = result["performance_vs_target_pct"].rank(method="min", ascending=False).astype(int)

    for column in ["revenue", "previous_revenue", "target_revenue", "performance_vs_target_pct", "week_over_week_pct"]:
        result[column] = result[column].map(_round)
    return result.sort_values(["rank", "department"]).reset_index(drop=True)


def scaled_revenue_targets(
    days: int,
    departments: list[str] | set[str] | tuple[str, ...] | None = None,
) -> dict[str, float]:
    """Scale weekly demo revenue targets to the selected reporting-window length."""
    if days <= 0:
        raise ValueError("days must be positive")
    selected = set(DEFAULT_WEEKLY_REVENUE_TARGETS) if departments is None else set(departments)
    missing = selected - set(DEFAULT_WEEKLY_REVENUE_TARGETS)
    if missing:
        raise ValueError(f"missing revenue target for department(s): {', '.join(sorted(missing))}")
    factor = days / 7
    return {department: DEFAULT_WEEKLY_REVENUE_TARGETS[department] * factor for department in sorted(selected)}


def calculate_snapshot(
    frames: Mapping[str, pd.DataFrame],
    window: DateWindow,
    *,
    department: str | None = None,
    region: str | None = None,
) -> KPISnapshot:
    """Calculate one KPI snapshot from already-loaded trusted reporting frames."""
    previous_window = window.previous()

    current_sales = filter_period(frames["sales"], "created_date", window, department=department, region=region)
    previous_sales = filter_period(
        frames["sales"], "created_date", previous_window, department=department, region=region
    )
    current_support = filter_period(frames["support"], "opened_at", window, department=department, region=region)
    current_operations = filter_period(
        frames["operations"], "scheduled_date", window, department=department, region=region
    )
    current_staffing = filter_period(frames["staffing"], "date", window, department=department, region=region)

    sales_scope = filter_scope(frames["sales"], department=department, region=region)
    scope_departments = sorted(sales_scope["department"].dropna().astype(str).unique().tolist())
    targets = scaled_revenue_targets(window.days, scope_departments)
    departments = calculate_department_performance(current_sales, previous_sales, revenue_targets=targets)

    return KPISnapshot(
        current_window=window,
        previous_window=previous_window,
        sales=calculate_sales_kpis(current_sales, previous_sales),
        support=calculate_support_kpis(current_support),
        operations=calculate_operations_kpis(current_operations, current_staffing),
        departments=departments.to_dict(orient="records"),
    )


class KPIEngine:
    """Read trusted reporting tables and calculate deterministic KPI snapshots."""

    def __init__(self, reporting_db: Path | str) -> None:
        self.reporting_db = Path(reporting_db)

    def load_frames(self) -> dict[str, pd.DataFrame]:
        if not self.reporting_db.exists():
            raise FileNotFoundError(f"reporting database not found: {self.reporting_db}")
        with sqlite3.connect(self.reporting_db) as conn:
            return {
                "sales": pd.read_sql_query("SELECT * FROM sales_clean", conn),
                "support": pd.read_sql_query("SELECT * FROM support_clean", conn),
                "operations": pd.read_sql_query("SELECT * FROM operations_clean", conn),
                "staffing": pd.read_sql_query("SELECT * FROM staffing_clean", conn),
            }

    def snapshot(
        self,
        window: DateWindow,
        *,
        department: str | None = None,
        region: str | None = None,
    ) -> KPISnapshot:
        return calculate_snapshot(
            self.load_frames(),
            window,
            department=department,
            region=region,
        )

    def latest_week(self) -> KPISnapshot:
        frames = self.load_frames()
        latest_date = pd.to_datetime(frames["sales"]["created_date"], errors="raise").max()
        return calculate_snapshot(frames, DateWindow.ending_on(latest_date, days=7))
