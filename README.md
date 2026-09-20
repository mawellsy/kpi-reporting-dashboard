# Automated Business KPI Reporting & Management Dashboard

A portfolio project that automates a multi-source business reporting workflow: ingestion, cleaning, KPI calculation, anomaly detection, dashboarding, AI-assisted management summaries, and scheduled reporting.

## Current milestone

**Milestone 3: KPI engine**

The project now has three working layers:

1. **Synthetic source generation** creates 112 days of reproducible business data.
2. **ETL (Extract, Transform, Load)** validates four source types, quarantines invalid rows, and loads trusted reporting tables into SQLite.
3. **KPI engine** calculates reusable sales, support, operations, and department metrics from clean data.

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

## Design principle

Business metrics are calculated deterministically in Python/SQL. The later LLM layer will receive only validated metric results and interpret them; it will not calculate or invent management numbers.
