import json
import sqlite3
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from kpi_dashboard.data_generation import GenerationConfig, SyntheticDataGenerator


def test_generator_creates_all_sources(tmp_path):
    generator = SyntheticDataGenerator(tmp_path, GenerationConfig(days=95, seed=7))
    paths = generator.generate_all()

    assert set(paths) == {"sales", "support", "operations", "staffing"}
    assert all(path.exists() for path in paths.values())


def test_generated_data_has_required_coverage_and_quality_problems(tmp_path):
    generator = SyntheticDataGenerator(tmp_path, GenerationConfig(days=95, seed=7))
    paths = generator.generate_all()

    sales = pd.read_csv(paths["sales"])
    staffing = pd.read_csv(paths["staffing"])
    support = pd.DataFrame(json.loads(paths["support"].read_text(encoding="utf-8")))
    with sqlite3.connect(paths["operations"]) as conn:
        operations = pd.read_sql_query("SELECT * FROM operations_jobs", conn)

    assert sales["created_date"].nunique() >= 90
    assert staffing["date"].nunique() >= 90
    assert sales["department"].nunique() == 4
    assert staffing["hours_worked"].isna().any()
    assert sales["customer_segment"].isna().any()
    assert (sales["revenue"] >= 50000).any()
    assert (support["satisfaction_score"] > 5).any()
    assert (operations["actual_hours"] < 0).any()


def test_generation_is_deterministic(tmp_path):
    first = tmp_path / "first"
    second = tmp_path / "second"

    SyntheticDataGenerator(first, GenerationConfig(days=20, seed=99)).generate_all()
    SyntheticDataGenerator(second, GenerationConfig(days=20, seed=99)).generate_all()

    assert (first / "sales.csv").read_bytes() == (second / "sales.csv").read_bytes()
    assert (first / "staffing.csv").read_bytes() == (second / "staffing.csv").read_bytes()
