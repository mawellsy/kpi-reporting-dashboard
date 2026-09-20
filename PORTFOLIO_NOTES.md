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

## Milestone 3 — Problems solved
- Converted trusted operational records into reusable management KPIs.
- Centralized metric definitions so charts and reports will use identical formulas.
- Added equal-period week-over-week comparisons instead of comparing mismatched date ranges.
- Added a cross-source productivity metric that combines completed jobs with staffing hours.
- Added explicit department revenue targets and ranking by target attainment.
- Kept all authoritative arithmetic deterministic and outside the future LLM summary layer.
- Removed noisy `Timedelta` deprecation warnings from synthetic data generation.

## Milestone 3 — Skills demonstrated
- reusable analytics functions
- business metric definition
- period-over-period comparison
- pandas aggregation and filtering
- cross-source KPI calculation
- explicit handling of undefined percentage change
- unit and integration testing for analytics code

## Milestone 3 — Demo moments
- run `python scripts/calculate_kpis.py` after ETL
- show the current and previous seven-day windows
- show revenue growth, conversion rate, support resolution time, and operations productivity
- show department performance versus explicit targets
- explain that the same tested KPI functions will feed both the dashboard and AI management summary


## Milestone 4 — Problems solved
- Turned the tested KPI engine into a usable management dashboard instead of duplicating formulas in UI code.
- Added one shared date/department/region filter model across all management pages.
- Added an equal-length comparison period for arbitrary user-selected date ranges.
- Scaled weekly department targets to the selected reporting-window length.
- Preserved zero-activity calendar days in chart series so trends do not silently skip dates.
- Added chart-ready daily sales, support, and operations datasets with automated tests.

## Milestone 4 — Skills demonstrated
- Streamlit application development
- Plotly business visualization
- presentation-layer architecture
- reusable analytics integration
- interactive filtering
- time-series preparation
- dashboard data testing

## Milestone 4 — Demo moments
- open the Executive Overview and explain the top-line KPI cards
- switch department or region and show every chart/KPI update from the same filter context
- change the date range and explain equal-period comparison plus target scaling
- open the Department Comparison page and show revenue versus target and prior-period change
- emphasize that charts consume the same deterministic KPI layer used by automated reporting

## Milestone 4 — Upwork talking points
- I can turn validated operational data into management dashboards without duplicating metric logic across reports and charts.
- I design filter behavior so users compare consistent populations and equal time periods.
- I keep business calculations testable and independent from the visualization framework, which makes future API or frontend changes safer.

## Milestone 5 — Problems solved
- Added deterministic anomaly rules without introducing unnecessary machine learning.
- Separated invalid-data handling from unusual-but-valid business behavior.
- Added three explainable rule families: threshold change, recent-average deviation, and missed target.
- Compared delayed jobs against prior equal-length periods so the baseline matches the selected reporting window.
- Reused the dashboard's date/department/region filter context for anomaly detection.
- Surfaced anomaly explanations directly on the Executive Overview.

## Milestone 5 — Skills demonstrated
- rule-based anomaly detection
- historical baseline construction
- deterministic alert thresholds
- time-window comparison
- explainable management alerts
- dashboard integration
- automated testing of detection rules

## Milestone 5 — Demo moments
- run `python scripts/detect_anomalies.py` and show structured anomaly output
- explain the difference between invalid source data and a valid business anomaly
- show the latest revenue decline threshold breach
- show delayed jobs compared with the previous four equal-length periods
- show Southeast and Southwest below scaled revenue targets
- change dashboard filters and show the anomaly set change with the selected business scope

## Milestone 5 — Upwork talking points
- I build anomaly systems with explicit, auditable business rules before reaching for machine learning.
- I compare current performance with structurally comparable historical periods rather than arbitrary baselines.
- I keep alert explanations tied to calculated values and references so managers can see why a flag was raised.
