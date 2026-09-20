# Automated Business KPI Reporting & Management Dashboard

A portfolio project that automates a multi-source business reporting workflow: ingestion, cleaning, KPI calculation, anomaly detection, dashboarding, AI-assisted management summaries, and scheduled reporting.

## Current milestone

**Milestone 5: deterministic anomaly detection**

The project now has five working layers:

1. **Synthetic source generation** creates 112 days of reproducible business data.
2. **ETL (Extract, Transform, Load)** validates four source types, quarantines invalid rows, and loads trusted reporting tables into SQLite.
3. **KPI engine** calculates reusable sales, support, operations, and department metrics from clean data.
4. **Streamlit dashboard** exposes the same tested KPI logic through management pages, charts, and shared filters.
5. **Anomaly detection** applies explicit threshold, recent-average, and missed-target rules to validated KPI results.

## Raw sources

- `data/raw/sales.csv` — sales opportunities and revenue
- `data/raw/support_tickets.json` — support tickets, later exposed through a mock REST API
- `data/raw/operations.db` — operational jobs
- `data/raw/staffing.csv` — daily staffing and absence data

## Processed database

Running ETL creates `data/processed/reporting.db` with:

- `sales_clean`
- `support_clean`
- `operations_clean`
- `staffing_clean`
- `etl_rejections`
- `etl_runs`
- `etl_run_source_stats`

Invalid records are retained with explicit rejection reasons and their original values. They never enter KPI calculations.

## KPI definitions

The KPI engine calculates metrics deterministically from trusted records.

### Sales

- **Revenue:** sum of sales revenue in the selected period.
- **Revenue growth:** percentage change in revenue versus the previous equal-length period.
- **Average transaction value:** average revenue among converted opportunities.
- **Conversion rate:** converted opportunities divided by all opportunities.

### Support

- **Ticket volume:** tickets opened in the selected period.
- **Average resolution time:** mean hours between opening and resolution for resolved tickets.
- **Unresolved tickets:** tickets not in `resolved` status.
- **Customer satisfaction:** mean available satisfaction score.

### Operations

- **Jobs completed:** completed jobs in the selected period.
- **Completion rate:** completed jobs divided by all scheduled jobs.
- **Delayed jobs:** jobs carrying the validated delayed flag.
- **Productivity:** completed jobs per 100 staffing hours.

### Department comparison

Each department is compared using:

- revenue
- revenue versus a fictional weekly management target
- week-over-week revenue change
- rank by performance versus target

The weekly target values are explicit demo assumptions in `kpis.py`; they are not inferred or invented by an LLM.

## Run

Generate/reset source data:

```bash
python scripts/generate_demo_data.py
```

Run ETL:

```bash
python scripts/run_etl.py
```

Calculate the latest seven-day KPI snapshot:

```bash
python scripts/calculate_kpis.py
```

Run tests:

```bash
pytest
```


## Dashboard

The dashboard has five pages:

1. Executive Overview
2. Sales
3. Operations
4. Customer Support
5. Department Comparison

Shared sidebar filters control:

- date range
- department
- region

The selected date range is compared with the immediately preceding equal-length period. Weekly demo revenue targets are scaled to the selected number of days so target comparisons remain meaningful outside a seven-day window. Quiet days remain visible in chart series with zero activity instead of disappearing from the calendar.

Run the dashboard after generating data and running ETL:

```bash
pip install -r requirements.txt
python scripts/generate_demo_data.py
python scripts/run_etl.py
streamlit run dashboard/app.py
```

## Anomaly detection

The anomaly layer is deterministic and intentionally simple. It currently checks:

- **Threshold change:** company revenue growth at or below a configured decline threshold.
- **Recent average deviation:** delayed jobs materially above the mean of recent equal-length reporting periods.
- **Missed targets:** departments below their scaled revenue target.

Rules operate on validated KPI outputs; they do not replace source-data validation. Thresholds are explicit in `src/kpi_dashboard/anomalies.py`, making each flag auditable and testable.

Run the latest seven-day anomaly scan:

```bash
python scripts/detect_anomalies.py
```

The Executive Overview also shows triggered anomalies using the same date, department, and region filters as the rest of the dashboard.

## Design principle

Business metrics are calculated deterministically in Python/SQL. The later LLM layer will receive only validated metric results and interpret them; it will not calculate or invent management numbers.
