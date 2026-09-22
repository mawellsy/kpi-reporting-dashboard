# Learning Notes

## Milestone 1 — Synthetic data

### Synthetic data
Artificial records that reproduce useful characteristics of real business data without exposing real customer or company information.

### Deterministic generation
A fixed random seed makes generated data repeatable. Repeatability matters for tests, screenshots, demonstrations, and debugging.

### Business relationships
Useful demo data should not be four unrelated random tables. In this project, staffing pressure influences support resolution and operational delays, which gives later KPI/anomaly layers a causal pattern to expose.

## Milestone 2 — ETL

### ETL
**Extract → Transform → Load** is a common data pipeline pattern.

- **Extract:** read data from source systems without changing business meaning.
- **Transform:** standardize types and validate structural/business rules.
- **Load:** write trusted records into the reporting database.

### Validation vs anomaly detection
These solve different problems.

**Validation asks:** “Is this record trustworthy enough to use?”

Examples:
- satisfaction score of 8 on a 1–5 scale → invalid
- negative job duration → invalid
- missing required sales segment → invalid

**Anomaly detection asks:** “Is this valid value unusual enough to investigate?”

Example:
- a $50,000 converted sale → unusual but possible, so it remains in clean data

Pattern:

```text
raw record
   ↓
valid structure/business rules?
   ├─ no  → quarantine + reason
   └─ yes → clean reporting table
                 ↓
           unusual pattern?
              ├─ yes → anomaly flag later
              └─ no  → normal metric input
```

### Quarantine
Quarantine means invalid rows are preserved outside the clean reporting tables. This is preferable to silently deleting them because the pipeline remains auditable: we can identify what failed, why it failed, and which source produced it.

### Fail-fast schema validation
If an entire required column disappears, the pipeline raises an error rather than pretending the source is usable. Row-level bad values are quarantined; source-level structural breakage stops the run.

### Idempotent demo loading
For this portfolio project, each ETL run recreates the processed SQLite database from the raw demo sources. That makes demos and tests predictable. A production incremental pipeline would usually preserve history and load only new/changed records.

### What to study
- pandas type conversion and boolean masks
- SQL tables and indexes
- primary/unique identifiers
- row-level vs schema-level validation
- why observability and rejected-record storage matter in data systems

## Milestone 3 — KPI engine

### KPI
A **Key Performance Indicator (KPI)** is a deliberately defined measurement used to monitor an important business outcome. A KPI is not merely any number on a dashboard; its formula, population, time window, and units must be explicit.

Example:

```text
conversion rate = converted opportunities / all opportunities × 100
```

Changing the denominator changes the meaning, so metric definitions belong in reusable code rather than being recreated independently in each chart.

### Current period vs comparison period
Revenue growth requires two equal-length windows:

```text
previous 7 days → baseline
current 7 days  → measured period

% change = (current - previous) / previous × 100
```

When the previous value is zero, percentage growth is undefined. The KPI engine returns `None` instead of fabricating an infinite or misleading percentage.

### Cross-source KPI
Productivity combines two trusted datasets:

```text
completed jobs / staffing hours × 100
```

This is an example of why ETL normalization matters. Once operations and staffing use consistent dates and department names, the reporting layer can combine them safely.

### Deterministic calculation vs AI interpretation
The application calculates every KPI itself. A later LLM receives the completed metric snapshot and may explain changes, but it does not perform the authoritative arithmetic.

```text
clean data
   ↓
deterministic KPI functions
   ↓
validated metric snapshot
   ↓
AI interpretation later
```

This separation reduces hallucination risk and makes every reported number testable.

### Targets
The project uses explicit fictional weekly revenue targets for department comparison. A target is a management assumption, not a fact derived from the dataset. Keeping targets visible in configuration/code makes the comparison auditable.

### What to study
- numerator and denominator selection in KPI definitions
- time-window filtering
- percentage change and divide-by-zero behavior
- pandas `groupby`
- why pure/reusable calculation functions are easier to test
- cross-source metrics and consistent dimensions


## Milestone 4 — Dashboard

### Presentation layer vs business logic
A dashboard should display metrics, not redefine them. The Streamlit application consumes the same tested KPI functions used by scripts and future reports. This creates one source of truth for formulas.

```text
trusted SQL data
      ↓
KPI calculation layer
      ↓
chart-ready dashboard data
      ↓
Streamlit presentation
```

If a formula were copied into each chart, the dashboard, scheduled report, and AI summary could disagree while all appearing plausible. Centralizing the calculation prevents that class of reporting drift.

### Shared filters
Date, department, and region are dimensions that change the population included in a KPI. The filter is applied before aggregation so every metric and chart on the page describes the same slice of the business.

### Equal comparison periods
A selected 14-day period is compared with the preceding 14 days, not with an arbitrary seven-day baseline. This keeps percentage-change comparisons structurally fair.

### Target scaling
Department targets are defined weekly. For a selected reporting window, the dashboard scales them proportionally:

```text
selected target = weekly target × selected days / 7
```

The targets remain explicit fictional management assumptions, not values inferred by AI.

### Continuous time series
A day with zero tickets is still a real calendar day. Chart data therefore fills the complete selected date range and represents no activity as zero rather than omitting the date. This prevents misleading gaps and makes day-to-day comparisons easier to read.

### What to study
- separation of business logic from presentation
- dashboard filter semantics
- time-series aggregation and missing dates
- Plotly figure construction
- Streamlit rerun/caching model
- why consistent KPI definitions matter across every reporting surface

## Milestone 5 — Anomaly detection

### Validation vs anomaly detection
Validation asks whether a record is trustworthy enough to enter reporting. Anomaly detection starts only after validation and asks whether trustworthy business behavior is unusual enough to investigate.

```text
raw data
   ↓
validation
   ├─ invalid → quarantine
   └─ valid
        ↓
       KPIs
        ↓
anomaly rules
   ├─ normal → no alert
   └─ unusual → explainable flag
```

A high number of delayed jobs can be valid data and still deserve management attention. Treating every unusual value as invalid would erase exactly the events the reporting system is meant to reveal.

### Rule-based detection
This project begins with explicit rules rather than machine learning because the rules are easy to explain, test, and tune with business owners.

Current rule families:

1. **Threshold change** — compare a KPI with a fixed business threshold.
2. **Recent-average deviation** — compare the current period with recent equal-length periods.
3. **Missed target** — compare actual performance with an explicit management target.

### Comparable historical baselines
A seven-day reporting period is compared with prior seven-day periods. A fourteen-day reporting period is compared with prior fourteen-day periods. Matching window length avoids creating an anomaly merely because one period contains more days.

### Heuristics are assumptions
An anomaly threshold is not a mathematical truth. For example, “30% above the recent average” is a configurable business heuristic. Production thresholds should be tuned using business impact, false-positive cost, seasonality, and stakeholder feedback.

### Why not machine learning yet?
Machine learning is useful when behavior is complex enough that explicit rules become brittle or incomplete. It also introduces model training, evaluation, drift, and explainability requirements. For this portfolio system, transparent deterministic rules solve the stated business need with less operational risk.

### What to study
- false positives and false negatives
- baselines and seasonality
- threshold tuning
- rolling averages and equal-period comparisons
- rule-based detection vs statistical/ML anomaly detection
- why anomaly explanations matter for operational adoption


## Milestone 6 — Grounded AI management summary

### The LLM is downstream of the truth layer
The model is not a calculator or source-of-record. Python produces validated KPIs and anomaly findings first. Only that small structured fact package crosses the AI boundary.

```text
trusted SQL data
      ↓
deterministic KPIs
      ↓
deterministic anomalies
      ↓
validated JSON context
      ↓
LLM interpretation
      ↓
local schema + numeric grounding validation
      ↓
management summary
```

This architecture reduces hallucination risk and makes the AI component replaceable. If the model/provider changes, the KPI definitions remain untouched.

### Structured output
The provider is asked for strict JSON matching four fields: `executive_summary`, `positive_changes`, `risks`, and `recommended_attention`. The application validates the result again locally instead of assuming the remote schema guarantee is sufficient.

### Numeric grounding
A model can produce valid JSON and still invent a business number. The local grounding guard extracts numeric claims from the prose and rejects any value that was absent from the supplied KPI/anomaly context. This is deliberately conservative for a management-reporting workflow.

### Provider abstraction
Business logic depends on a small `SummaryProvider` protocol rather than directly on the OpenAI client. Tests use a fake provider, so the suite is deterministic, fast, and does not spend API credits. The OpenAI adapter is only infrastructure.

### What to study
- prompt/context boundaries
- Structured Outputs / JSON Schema
- dependency inversion and provider adapters
- deterministic tests with fake external services
- hallucination vs schema validation
- why numeric grounding is stricter than valid JSON
- API-key management through environment variables

## Phase 2 — Milestone 9: PostgreSQL reporting database

### Why introduce a database abstraction?
The original project opened SQLite files directly with `sqlite3`. That is fine for a single-process demo, but it couples application code to one storage engine. Milestone 9 moves reporting access behind SQLAlchemy URLs and engines so the same ETL and KPI code can target PostgreSQL in a deployed environment while tests can remain fast and isolated with SQLite.

### PostgreSQL vs SQLite
SQLite is an embedded database stored in one local file. It is excellent for tests, prototypes, and small single-user tools. PostgreSQL is a database server designed for concurrent clients and networked applications. It provides stronger operational tooling, connection handling, permissions, backup options, and a more realistic deployment target for a shared management dashboard.

### Connection URLs
`REPORTING_DATABASE_URL` is configuration, not business logic. A PostgreSQL URL such as `postgresql+psycopg://user:password@host:5432/database` tells SQLAlchemy which dialect and driver to use. The password belongs in `.env` or a deployment secret store and must never be committed.

### Why keep SQLite in tests?
The important business behavior is deterministic validation, loading, querying, and KPI calculation. SQLite lets the test suite exercise that behavior quickly without requiring a running external service. PostgreSQL-specific integration can be smoke-tested separately when the service is available.

### Indexes
Indexes trade additional storage/write work for faster lookup and filtering. This project keeps unique indexes on business identifiers and adds/retains indexes around common reporting filters such as date + department. Indexes should be justified by query patterns rather than added to every column reflexively.

### What to study
- client/server databases vs embedded databases
- SQLAlchemy engine and connection lifecycle
- database URLs and drivers
- PostgreSQL connection strings
- transactions
- indexes and uniqueness
- why unit tests and production infrastructure do not have to use the same database server
