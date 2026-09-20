import json
import sqlite3
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from kpi_dashboard.data_generation import GenerationConfig, SyntheticDataGenerator
from kpi_dashboard.etl import ETLConfig, ETLPipeline


def _run_pipeline(tmp_path: Path):
    raw_dir = tmp_path / "raw"
    output_db = tmp_path / "processed" / "reporting.db"
    SyntheticDataGenerator(raw_dir, GenerationConfig(days=95, seed=7)).generate_all()
    result = ETLPipeline(ETLConfig(raw_dir=raw_dir, output_db=output_db)).run()
    return raw_dir, output_db, result


def test_etl_quarantines_known_bad_rows_and_preserves_valid_anomaly(tmp_path):
    _, output_db, result = _run_pipeline(tmp_path)

    assert result.rejected_rows == {
        "sales": 1,
        "support": 1,
        "operations": 1,
        "staffing": 1,
    }

    with sqlite3.connect(output_db) as conn:
        rejections = pd.read_sql_query("SELECT * FROM etl_rejections", conn)
        sales = pd.read_sql_query("SELECT * FROM sales_clean", conn)

    assert len(rejections) == 4
    assert set(rejections["source"]) == {"sales", "support", "operations", "staffing"}
    assert (sales["revenue"] == 50000.0).any(), "high but valid revenue belongs in clean data"


def test_clean_tables_satisfy_critical_quality_rules(tmp_path):
    _, output_db, _ = _run_pipeline(tmp_path)

    with sqlite3.connect(output_db) as conn:
        sales = pd.read_sql_query("SELECT * FROM sales_clean", conn)
        support = pd.read_sql_query("SELECT * FROM support_clean", conn)
        operations = pd.read_sql_query("SELECT * FROM operations_clean", conn)
        staffing = pd.read_sql_query("SELECT * FROM staffing_clean", conn)
        run_stats = pd.read_sql_query("SELECT * FROM etl_runs", conn)

    assert sales["opportunity_id"].is_unique
    assert support["ticket_id"].is_unique
    assert operations["job_id"].is_unique
    assert not staffing.duplicated(["date", "department"]).any()
    assert sales["customer_segment"].notna().all()
    assert support["satisfaction_score"].dropna().between(1, 5).all()
    assert (operations["actual_hours"] >= 0).all()
    assert staffing["hours_worked"].notna().all()
    assert int(run_stats.loc[0, "total_rejected"]) == 4


def test_duplicate_sales_record_is_detected_and_quarantined(tmp_path):
    raw_dir = tmp_path / "raw"
    SyntheticDataGenerator(raw_dir, GenerationConfig(days=20, seed=10)).generate_all()

    sales_path = raw_dir / "sales.csv"
    sales = pd.read_csv(sales_path)
    duplicate = sales.iloc[[0]].copy()
    sales = pd.concat([sales, duplicate], ignore_index=True)
    sales.to_csv(sales_path, index=False)

    output_db = tmp_path / "reporting.db"
    result = ETLPipeline(ETLConfig(raw_dir=raw_dir, output_db=output_db)).run()

    assert result.rejected_rows["sales"] >= 2  # duplicate plus generated missing segment row
    with sqlite3.connect(output_db) as conn:
        rejections = pd.read_sql_query(
            "SELECT reasons FROM etl_rejections WHERE source = 'sales'", conn
        )
    reasons = " ".join(rejections["reasons"].tolist())
    assert "duplicate opportunity_id" in reasons


def test_missing_required_source_column_fails_fast(tmp_path):
    raw_dir = tmp_path / "raw"
    SyntheticDataGenerator(raw_dir, GenerationConfig(days=20, seed=10)).generate_all()
    sales_path = raw_dir / "sales.csv"
    sales = pd.read_csv(sales_path).drop(columns=["revenue"])
    sales.to_csv(sales_path, index=False)

    pipeline = ETLPipeline(ETLConfig(raw_dir=raw_dir, output_db=tmp_path / "reporting.db"))

    try:
        pipeline.run()
    except ValueError as exc:
        assert "missing required columns" in str(exc)
        assert "revenue" in str(exc)
    else:
        raise AssertionError("ETL should fail when a required source column is missing")
