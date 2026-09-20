# Automated Business KPI Reporting & Management Dashboard

A portfolio project that automates a multi-source business reporting workflow: ingestion, cleaning, KPI calculation, anomaly detection, dashboarding, AI-assisted management summaries, and scheduled reporting.

## Current milestone

**Milestone 2: ETL pipeline**

The project now has two working layers:

1. **Synthetic source generation** creates 112 days of reproducible business data.
2. **ETL (Extract, Transform, Load)** reads every source, validates business/data-quality rules, quarantines invalid records, and loads clean reporting tables into SQLite.

### Raw sources

- `data/raw/sales.csv` — sales opportunities and revenue
- `data/raw/support_tickets.json` — support tickets, later exposed through a mock REST API
- `data/raw/operations.db` — operational jobs
- `data/raw/staffing.csv` — daily staffing and absence data

### Processed database

Running ETL creates `data/processed/reporting.db` with:

- `sales_clean`
- `support_clean`
- `operations_clean`
- `staffing_clean`
- `etl_rejections`
- `etl_runs`
- `etl_run_source_stats`

Invalid records are retained with explicit rejection reasons and their original values. They never enter KPI calculations.

A large but valid transaction remains in clean data. It is an **anomaly**, not a data-quality failure, and will be handled by the later anomaly-detection layer.

## Run

Generate/reset source data:

```bash
python scripts/generate_demo_data.py
```

Run ETL:

```bash
python scripts/run_etl.py
```

Run tests:

```bash
pytest
```

## Design principle

Metrics will be calculated deterministically in Python/SQL. The LLM will receive only validated metric results and will interpret them, not calculate business facts itself.
