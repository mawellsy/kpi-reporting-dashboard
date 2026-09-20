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
