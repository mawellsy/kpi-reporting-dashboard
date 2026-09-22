from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from kpi_dashboard.database import (
    database_display_name,
    normalize_database_url,
    resolve_reporting_database_url,
    sqlite_database_path,
)


def test_local_path_normalizes_to_absolute_sqlite_url(tmp_path):
    database_path = tmp_path / "reporting.db"

    database_url = normalize_database_url(database_path)

    assert database_url.startswith("sqlite+pysqlite:///")
    assert sqlite_database_path(database_url) == database_path.resolve()


def test_reporting_database_environment_overrides_sqlite_fallback(tmp_path):
    configured = "postgresql+psycopg://reporter:secret@localhost:5432/kpi_reporting"

    database_url = resolve_reporting_database_url(
        tmp_path,
        environ={"REPORTING_DATABASE_URL": configured},
    )

    assert database_url == configured


def test_plain_postgresql_url_uses_psycopg_driver():
    database_url = normalize_database_url(
        "postgresql://reporter:secret@localhost:5432/kpi_reporting"
    )

    assert database_url.startswith("postgresql+psycopg://")


def test_database_display_name_hides_password():
    display = database_display_name(
        "postgresql+psycopg://reporter:super-secret@db.example:5432/kpi_reporting"
    )

    assert "super-secret" not in display
    assert "***" in display
