# Learning Notes

## Milestone 1 concepts

### Synthetic data
Synthetic data is generated rather than collected from real customers. It allows a portfolio project to demonstrate realistic business logic without exposing confidential information.

### Determinism
A fixed random seed makes pseudo-random output repeatable. Reproducibility matters because tests, screenshots, and demos should not change unpredictably every time the generator runs.

### Raw vs cleaned data
Raw source data should preserve the defects that arrived from the source. The ETL layer is responsible for detecting, rejecting, repairing, or quarantining bad records. Cleaning inside the generator would hide the exact failure cases the project is intended to demonstrate.

### Cross-domain relationships
The datasets are not independent noise. Higher staff absence can reduce sales conversion and increase support resolution time and operational delays. This gives later KPI and anomaly logic causal-looking business patterns to explain.

### What to study
- pandas DataFrame creation and grouping
- SQLite tables and indexes
- random distributions: Poisson, binomial, log-normal, gamma
- why deterministic fixtures improve automated testing
