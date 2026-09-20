# Portfolio Notes

## Project purpose
Automate a multi-source management reporting workflow from raw operational data through validated decision support.

## Milestone 1 — Problems solved
- Created repeatable synthetic business data instead of relying on confidential real data.
- Represented several realistic source types: CSV, JSON/API-shaped data, and SQLite.
- Embedded relationships between staffing, operations, support, and sales.
- Injected controlled data-quality problems for later validation demonstrations.

## Milestone 2 — Problems solved
- Automated ingestion of four source types into one reporting pipeline.
- Separated invalid source records from trusted reporting records.
- Added explicit rejection reasons instead of silently dropping bad data.
- Added ETL run statistics for basic traceability.
- Preserved valid outliers for a later anomaly-detection step.
- Added database indexes that support identifier integrity and reporting filters.

## Skills demonstrated
- Python
- pandas
- SQLite / SQL
- multi-source ETL
- deterministic data validation
- data-quality rules
- rejected-record/quarantine patterns
- automated testing with pytest
- reproducible demo architecture

## Architectural decisions
- Keep ETL validation deterministic; do not use an LLM to decide whether numeric/source data is valid.
- Fail the pipeline for missing required columns because that is a source-contract failure.
- Quarantine individual invalid rows so one bad record does not destroy the entire reporting refresh.
- Recreate the processed database during this demo stage for predictable, idempotent runs.
- Treat high-but-valid values as anomaly-detection candidates, not ETL errors.

## Measurable business benefits to demonstrate later
- reduction in manual spreadsheet consolidation
- faster weekly report preparation
- fewer reporting errors caused by malformed source records
- traceable rejected records instead of silent data loss

## Demo/screenshots to capture later
- raw invalid source rows
- terminal ETL summary showing loaded vs rejected records
- `etl_rejections` table with human-readable reasons
- clean reporting tables proving bad rows were excluded
- dashboard anomaly caused by the synthetic Southwest staffing issue

## Potential Upwork proposal talking points
- I can consolidate CSV/API/database sources into a validated reporting layer.
- I design reporting pipelines so bad source data is visible and auditable rather than silently contaminating KPIs.
- I separate deterministic calculations from AI interpretation so management numbers remain trustworthy.
