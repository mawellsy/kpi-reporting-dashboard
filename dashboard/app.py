from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd
import plotly.express as px
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from kpi_dashboard.dashboard import build_dashboard_data, get_filter_options
from kpi_dashboard.kpis import DateWindow, KPIEngine


REPORTING_DB = ROOT / "data" / "processed" / "reporting.db"
PAGES = [
    "Executive Overview",
    "Sales",
    "Operations",
    "Customer Support",
    "Department Comparison",
]


def money(value: float | None) -> str:
    return "N/A" if value is None else f"${value:,.2f}"


def number(value: float | None, suffix: str = "") -> str:
    return "N/A" if value is None else f"{value:,.2f}{suffix}"


def delta(value: float | None, label: str = "vs previous period") -> str | None:
    return None if value is None else f"{value:+.2f}% {label}"


@st.cache_data(show_spinner=False)
def load_frames(db_path: str, modified_ns: int) -> dict[str, pd.DataFrame]:
    del modified_ns  # cache key only; reading remains delegated to the tested KPI engine.
    return KPIEngine(db_path).load_frames()


def metric_row(data) -> None:
    sales = data.snapshot.sales
    support = data.snapshot.support
    operations = data.snapshot.operations

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Revenue", money(sales.revenue), delta=delta(sales.revenue_growth_pct))
    c2.metric("Conversion rate", number(sales.conversion_rate_pct, "%"))
    c3.metric("Avg resolution", number(support.average_resolution_hours, " h"))
    c4.metric("Completion rate", number(operations.completion_rate_pct, "%"))


def render_anomalies(data) -> None:
    st.subheader("Anomalies requiring attention")
    if not data.anomalies:
        st.success("No configured anomaly rules were triggered for this selection.")
        return

    rows = []
    for item in data.anomalies:
        rows.append(
            {
                "Severity": item.severity.title(),
                "Rule": item.category.replace("_", " ").title(),
                "Scope": item.scope,
                "Metric": item.metric.replace("_", " ").title(),
                "Current": item.current_value,
                "Reference": item.reference_value,
                "Deviation %": item.deviation_pct,
                "Explanation": item.message,
            }
        )
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def render_executive(data) -> None:
    st.header("Executive Overview")
    metric_row(data)
    render_anomalies(data)

    left, right = st.columns(2)
    with left:
        st.subheader("Revenue trend")
        if data.sales_trend.empty:
            st.info("No sales records match the selected filters.")
        else:
            fig = px.line(data.sales_trend, x="date", y="revenue", markers=True, labels={"revenue": "Revenue"})
            st.plotly_chart(fig, use_container_width=True)

    with right:
        st.subheader("Department vs target")
        if data.department_performance.empty:
            st.info("No department data match the selected filters.")
        else:
            fig = px.bar(
                data.department_performance,
                x="department",
                y="performance_vs_target_pct",
                labels={"performance_vs_target_pct": "% vs target", "department": "Department"},
            )
            st.plotly_chart(fig, use_container_width=True)

    st.subheader("Operational pulse")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Support tickets", f"{data.snapshot.support.ticket_volume:,}")
    c2.metric("Unresolved tickets", f"{data.snapshot.support.unresolved_tickets:,}")
    c3.metric("Jobs completed", f"{data.snapshot.operations.jobs_completed:,}")
    c4.metric("Delayed jobs", f"{data.snapshot.operations.delayed_jobs:,}")


def render_sales(data) -> None:
    st.header("Sales")
    sales = data.snapshot.sales
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Revenue", money(sales.revenue), delta=delta(sales.revenue_growth_pct))
    c2.metric("Avg transaction", money(sales.average_transaction_value))
    c3.metric("Conversion rate", number(sales.conversion_rate_pct, "%"))
    c4.metric("Period length", f"{data.snapshot.current_window.days} days")

    if data.sales_trend.empty:
        st.info("No sales records match the selected filters.")
        return

    st.plotly_chart(
        px.line(data.sales_trend, x="date", y="revenue", markers=True, title="Daily revenue"),
        use_container_width=True,
    )
    volume = data.sales_trend.melt(
        id_vars="date",
        value_vars=["opportunities", "conversions"],
        var_name="series",
        value_name="count",
    )
    st.plotly_chart(
        px.bar(volume, x="date", y="count", color="series", barmode="group", title="Opportunity volume"),
        use_container_width=True,
    )


def render_operations(data) -> None:
    st.header("Operations")
    operations = data.snapshot.operations
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Jobs completed", f"{operations.jobs_completed:,}")
    c2.metric("Completion rate", number(operations.completion_rate_pct, "%"))
    c3.metric("Delayed jobs", f"{operations.delayed_jobs:,}")
    c4.metric("Productivity", number(operations.productivity_jobs_per_100_hours, " / 100 h"))

    if data.operations_trend.empty:
        st.info("No operations records match the selected filters.")
        return

    volume = data.operations_trend.melt(
        id_vars="date",
        value_vars=["jobs_completed", "delayed_jobs"],
        var_name="series",
        value_name="jobs",
    )
    st.plotly_chart(
        px.bar(volume, x="date", y="jobs", color="series", barmode="group", title="Daily operations"),
        use_container_width=True,
    )
    st.plotly_chart(
        px.line(
            data.operations_trend,
            x="date",
            y="completion_rate_pct",
            markers=True,
            title="Daily completion rate",
            labels={"completion_rate_pct": "Completion rate (%)"},
        ),
        use_container_width=True,
    )


def render_support(data) -> None:
    st.header("Customer Support")
    support = data.snapshot.support
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Ticket volume", f"{support.ticket_volume:,}")
    c2.metric("Avg resolution", number(support.average_resolution_hours, " h"))
    c3.metric("Unresolved", f"{support.unresolved_tickets:,}")
    c4.metric("CSAT", number(support.customer_satisfaction, " / 5"))

    if data.support_trend.empty:
        st.info("No support records match the selected filters.")
        return

    volume = data.support_trend.melt(
        id_vars="date",
        value_vars=["ticket_volume", "unresolved_tickets"],
        var_name="series",
        value_name="tickets",
    )
    st.plotly_chart(
        px.bar(volume, x="date", y="tickets", color="series", barmode="group", title="Daily support volume"),
        use_container_width=True,
    )
    st.plotly_chart(
        px.line(
            data.support_trend,
            x="date",
            y="customer_satisfaction",
            markers=True,
            title="Daily customer satisfaction",
            labels={"customer_satisfaction": "CSAT"},
        ),
        use_container_width=True,
    )


def render_departments(data) -> None:
    st.header("Department Comparison")
    table = data.department_performance
    if table.empty:
        st.info("No department data match the selected filters.")
        return

    st.plotly_chart(
        px.bar(
            table,
            x="department",
            y="performance_vs_target_pct",
            labels={"performance_vs_target_pct": "% vs target", "department": "Department"},
            title="Performance versus scaled revenue target",
        ),
        use_container_width=True,
    )
    st.dataframe(
        table.rename(
            columns={
                "department": "Department",
                "revenue": "Revenue",
                "target_revenue": "Target revenue",
                "performance_vs_target_pct": "% vs target",
                "week_over_week_pct": "% vs previous period",
                "rank": "Rank",
            }
        ),
        use_container_width=True,
        hide_index=True,
    )
    st.caption("Weekly demo revenue targets are scaled to the selected date-range length.")


def main() -> None:
    st.set_page_config(page_title="KPI Management Dashboard", page_icon="📊", layout="wide")
    st.title("Automated Business KPI Reporting")
    st.caption("Validated reporting data → deterministic KPIs → management dashboard")

    if not REPORTING_DB.exists():
        st.error("Reporting database not found. Run `python scripts/run_etl.py` first.")
        st.stop()

    frames = load_frames(str(REPORTING_DB), REPORTING_DB.stat().st_mtime_ns)
    options = get_filter_options(frames)
    default_start = max(options.minimum_date, options.maximum_date - pd.Timedelta(days=6))

    st.sidebar.header("Dashboard controls")
    page = st.sidebar.radio("Page", PAGES)
    selected_dates = st.sidebar.date_input(
        "Date range",
        value=(default_start.date(), options.maximum_date.date()),
        min_value=options.minimum_date.date(),
        max_value=options.maximum_date.date(),
    )
    department_choice = st.sidebar.selectbox("Department", ["All", *options.departments])
    region_choice = st.sidebar.selectbox("Region", ["All", *options.regions])

    if not isinstance(selected_dates, (tuple, list)) or len(selected_dates) != 2:
        st.info("Select both a start and end date.")
        st.stop()

    start_date, end_date = selected_dates
    window = DateWindow(pd.Timestamp(start_date), pd.Timestamp(end_date))
    department = None if department_choice == "All" else department_choice
    region = None if region_choice == "All" else region_choice
    data = build_dashboard_data(frames, window, department=department, region=region)

    st.sidebar.caption(
        f"Current: {window.start.date()} → {window.end.date()}\n\n"
        f"Comparison: {window.previous().start.date()} → {window.previous().end.date()}"
    )

    if page == "Executive Overview":
        render_executive(data)
    elif page == "Sales":
        render_sales(data)
    elif page == "Operations":
        render_operations(data)
    elif page == "Customer Support":
        render_support(data)
    else:
        render_departments(data)


if __name__ == "__main__":
    main()
