# Automated Business KPI Reporting & Management Dashboard

A portfolio project that automates a multi-source business reporting workflow: ingestion, cleaning, KPI calculation, anomaly detection, dashboarding, AI-assisted management summaries, and scheduled reporting.

## Current milestone

**Milestone 1: Synthetic dataset generator**

The generator creates 112 days of reproducible demo data across four source types:

- `sales.csv` — sales opportunities and converted revenue
- `support_tickets.json` — support tickets, later exposed through a mock REST API
- `operations.db` — SQLite source containing operational jobs
- `staffing.csv` — daily staffing and absence data

The generated data intentionally contains a small number of missing, anomalous, and impossible values so the ETL milestone has realistic validation work to perform.

## Run

```bash
python scripts/generate_demo_data.py
```

## Test

```bash
pytest
```

## Design principle

Metrics will be calculated deterministically in Python/SQL. The LLM will receive only validated metric results and will interpret them, not calculate business facts itself.
