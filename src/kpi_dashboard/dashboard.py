from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import pandas as pd

from .kpis import DateWindow, KPISnapshot, calculate_snapshot, filter_period


@dataclass(frozen=True)
class FilterOptions:
    minimum_date: pd.Timestamp
    maximum_date: pd.Timestamp
    departments: tuple[str, ...]
    regions: tuple[str, ...]


@dataclass(frozen=True)
class DashboardData:
    snapshot: KPISnapshot
    sales_trend: pd.DataFrame
    support_trend: pd.DataFrame
    operations_trend: pd.DataFrame
    department_performance: pd.DataFrame


def get_filter_options(frames: Mapping[str, pd.DataFrame]) -> FilterOptions:
    sales_dates = pd.to_datetime(frames["sales"]["created_date"], errors="raise").dt.normalize()
    departments = tuple(sorted(frames["sales"]["department"].dropna().astype(str).unique().tolist()))
    regions = tuple(sorted(frames["sales"]["region"].dropna().astype(str).unique().tolist()))
    return FilterOptions(
        minimum_date=sales_dates.min(),
        maximum_date=sales_dates.max(),
        departments=departments,
        regions=regions,
    )


def _calendar(window: DateWindow) -> pd.DataFrame:
    return pd.DataFrame({"date": pd.date_range(window.start, window.end, freq="D")})


def _sales_trend(sales: pd.DataFrame, window: DateWindow) -> pd.DataFrame:
    if sales.empty:
        result = _calendar(window)
        result[["revenue", "opportunities", "conversions"]] = 0
        result["conversion_rate_pct"] = pd.NA
        return result

    frame = sales.copy()
    frame["date"] = pd.to_datetime(frame["created_date"], errors="coerce").dt.normalize()
    frame["converted_bool"] = frame["converted"].fillna(False).astype(bool)
    frame["revenue"] = pd.to_numeric(frame["revenue"], errors="coerce").fillna(0.0)
    result = (
        frame.groupby("date", as_index=False)
        .agg(
            revenue=("revenue", "sum"),
            opportunities=("opportunity_id", "size"),
            conversions=("converted_bool", "sum"),
        )
        .sort_values("date")
    )
    result = _calendar(window).merge(result, on="date", how="left")
    result[["revenue", "opportunities", "conversions"]] = result[["revenue", "opportunities", "conversions"]].fillna(0)
    result["conversion_rate_pct"] = result["conversions"].div(result["opportunities"].replace(0, pd.NA)) * 100
    return result.round({"revenue": 2, "conversion_rate_pct": 2})


def _support_trend(support: pd.DataFrame, window: DateWindow) -> pd.DataFrame:
    if support.empty:
        result = _calendar(window)
        result[["ticket_volume", "unresolved_tickets"]] = 0
        result["customer_satisfaction"] = pd.NA
        return result

    frame = support.copy()
    frame["date"] = pd.to_datetime(frame["opened_at"], errors="coerce", utc=True).dt.tz_localize(None).dt.normalize()
    frame["unresolved"] = frame["status"].astype(str).ne("resolved").astype(int)
    frame["satisfaction_score"] = pd.to_numeric(frame["satisfaction_score"], errors="coerce")
    result = (
        frame.groupby("date", as_index=False)
        .agg(
            ticket_volume=("ticket_id", "size"),
            unresolved_tickets=("unresolved", "sum"),
            customer_satisfaction=("satisfaction_score", "mean"),
        )
        .sort_values("date")
    )
    result = _calendar(window).merge(result, on="date", how="left")
    result[["ticket_volume", "unresolved_tickets"]] = result[["ticket_volume", "unresolved_tickets"]].fillna(0)
    return result.round({"customer_satisfaction": 2})


def _operations_trend(operations: pd.DataFrame, window: DateWindow) -> pd.DataFrame:
    if operations.empty:
        result = _calendar(window)
        result[["jobs", "jobs_completed", "delayed_jobs"]] = 0
        result["completion_rate_pct"] = pd.NA
        return result

    frame = operations.copy()
    frame["date"] = pd.to_datetime(frame["scheduled_date"], errors="coerce").dt.normalize()
    frame["completed"] = frame["status"].astype(str).eq("completed").astype(int)
    frame["delayed_bool"] = frame["delayed"].fillna(False).astype(bool).astype(int)
    result = (
        frame.groupby("date", as_index=False)
        .agg(
            jobs=("job_id", "size"),
            jobs_completed=("completed", "sum"),
            delayed_jobs=("delayed_bool", "sum"),
        )
        .sort_values("date")
    )
    result = _calendar(window).merge(result, on="date", how="left")
    result[["jobs", "jobs_completed", "delayed_jobs"]] = result[["jobs", "jobs_completed", "delayed_jobs"]].fillna(0)
    result["completion_rate_pct"] = result["jobs_completed"].div(result["jobs"].replace(0, pd.NA)) * 100
    return result.round({"completion_rate_pct": 2})


def build_dashboard_data(
    frames: Mapping[str, pd.DataFrame],
    window: DateWindow,
    *,
    department: str | None = None,
    region: str | None = None,
) -> DashboardData:
    snapshot = calculate_snapshot(frames, window, department=department, region=region)

    sales = filter_period(frames["sales"], "created_date", window, department=department, region=region)
    support = filter_period(frames["support"], "opened_at", window, department=department, region=region)
    operations = filter_period(
        frames["operations"], "scheduled_date", window, department=department, region=region
    )

    return DashboardData(
        snapshot=snapshot,
        sales_trend=_sales_trend(sales, window),
        support_trend=_support_trend(support, window),
        operations_trend=_operations_trend(operations, window),
        department_performance=pd.DataFrame(snapshot.departments),
    )
