# Automated Business KPI Reporting & Management Dashboard

A portfolio project demonstrating an end-to-end management reporting workflow for a fictional multi-department company.

## Project status

**Complete portfolio implementation.**

The project demonstrates an end-to-end automated management reporting workflow:

**Multi-source data → validation → ETL → SQL → KPI calculation → anomaly detection → interactive dashboard → grounded AI management summary.**

## What this project solves

Operational information for the fictional company is spread across sales, customer support, operations, and staffing sources. Without automation, management reporting would require manually consolidating those sources, checking data quality, calculating KPIs, reviewing performance against recent history and targets, and writing a management summary.

This system automates that workflow while keeping the underlying KPI and anomaly calculations deterministic, testable, and auditable. The LLM is used only after validated metrics and anomaly results have been produced by the application.

## Portfolio highlights

- **Four source feeds:** sales CSV, support JSON/mock API data, operations SQLite data, and staffing CSV.
- **Validation and quarantine:** invalid records are retained with rejection reasons instead of contaminating reporting tables.
- **Deterministic KPI engine:** reusable Python/SQL calculations for sales, support, operations, and department performance.
- **Five-page Streamlit dashboard:** Executive Overview, Sales, Operations, Customer Support, and Department Comparison.
- **Shared filters:** date range, department, and region drive the dashboard and comparison scope.
- **Deterministic anomaly detection:** explicit threshold, recent-average deviation, and missed-target rules.
- **Grounded AI management summary:** the LLM receives only validated KPI and anomaly data in a structured package.
- **Local output validation:** unsupported numeric claims are rejected when they do not exist in the supplied facts.

## Dashboard preview

![Executive dashboard](docs/screenshots/executive-overview.png)

## Business value

As a portfolio implementation, this system demonstrates how an automated reporting workflow can:

- reduce repetitive spreadsheet and cross-system consolidation work
- standardize KPI calculations across reporting periods
- prevent invalid records from entering management metrics
- provide faster visibility into operational performance
- surface important anomalies automatically using explicit rules
- produce concise management summaries grounded in validated metrics

No measured ROI is claimed; the project uses synthetic data to demonstrate the workflow and engineering approach.

## Raw sources

- `data/raw/sales.csv` — sales opportunities and revenue
- `data/raw/support_tickets.json` — customer support tickets
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

## PostgreSQL reporting database

PostgreSQL is the intended reporting database for deployed or multi-user use. Database access is routed through SQLAlchemy so the ETL pipeline, KPI engine, dashboard, anomaly scan, and management-summary CLI use the same configured backend. SQLite remains available as a lightweight fallback for tests and a zero-setup local demo.

Configure PostgreSQL in `.env` with a SQLAlchemy connection URL:

```dotenv
REPORTING_DATABASE_URL=postgresql+psycopg://kpi_user:local-dev-password@localhost:5432/kpi_reporting
```

Then run the normal workflow:

```bash
python scripts/run_etl.py
python scripts/calculate_kpis.py
streamlit run dashboard/app.py
```

The reporting schema keeps explicit indexes for business identifiers and common reporting filters, including sales date/department, operations date/department, support department, and rejection source. PostgreSQL is a better production-style fit than a single local SQLite file because it supports concurrent clients, networked services, connection management, stronger operational tooling, and a cleaner path to containerized/deployed environments.

If `REPORTING_DATABASE_URL` is blank, the project falls back to `data/processed/reporting.db` so the existing local demo and automated tests remain self-contained.

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

The anomaly layer is deterministic and intentionally simple. It checks:

- **Threshold change:** company revenue growth at or below a configured decline threshold.
- **Recent average deviation:** delayed jobs materially above the mean of recent equal-length reporting periods.
- **Missed targets:** departments below their scaled revenue target.

Rules operate on validated KPI outputs; they do not replace source-data validation. Thresholds are explicit in `src/kpi_dashboard/anomalies.py`, making each flag auditable and testable.

Run the latest seven-day anomaly scan:

```bash
python scripts/detect_anomalies.py
```

The Executive Overview also shows triggered anomalies using the same date, department, and region filters as the rest of the dashboard.

## AI management summary

The LLM receives only an application-generated JSON package containing:

- selected department/region scope
- validated KPI snapshot
- validated anomaly results

It does **not** receive raw sales, ticket, operations, or staffing records. The response must match a strict JSON schema with exactly these fields:

- `executive_summary`
- `positive_changes`
- `risks`
- `recommended_attention`

The application also performs a local grounding check: numeric values in the generated prose must already exist in the supplied JSON. Invalid or unsupported output is retried and ultimately rejected rather than silently shown to management.

Create a local `.env` file from the committed template:

```bash
cp .env.example .env
```

Then put your real local values in `.env`:

```dotenv
OPENAI_API_KEY=your-real-key
OPENAI_MODEL=gpt-5-mini
```

The CLI and Streamlit dashboard load this file automatically with `python-dotenv`. `.env` is ignored by Git; `.env.example` contains only safe variable names/defaults and is committed as documentation. In deployed environments, inject these variables through the hosting platform instead of shipping a `.env` file.

Generate the latest seven-day summary from the CLI:

```bash
python scripts/generate_management_summary.py
```

The Executive Overview also exposes a **Generate AI management summary** button when `OPENAI_API_KEY` is present. Streamlit stores the generated result only for the matching filter scope so a summary from one department/date selection is not reused for another.

## Design principle

**Python/SQL calculate the business metrics and anomaly results. The LLM interprets validated facts.**

The LLM is not the authoritative calculator. It receives a constrained package of validated KPI and anomaly data, must return a strict structured response, and is subject to local grounding checks before its output is shown. This keeps the numerical reporting logic deterministic and auditable while using the model for concise management interpretation.
