from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine, make_url


REPORTING_DATABASE_ENV = "REPORTING_DATABASE_URL"


class ReportingDatabaseError(RuntimeError):
    """Raised when the configured reporting database cannot be used safely."""


def sqlite_url_for_path(path: Path | str) -> str:
    """Return an absolute SQLAlchemy SQLite URL for a local database path."""
    resolved = Path(path).expanduser().resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite+pysqlite:///{resolved.as_posix()}"


def normalize_database_url(value: Path | str) -> str:
    """Normalize a local path or SQLAlchemy URL to a supported reporting URL."""
    if isinstance(value, Path):
        return sqlite_url_for_path(value)

    raw = str(value).strip()
    if not raw:
        raise ValueError("reporting database value cannot be empty")
    if "://" not in raw:
        return sqlite_url_for_path(raw)

    url = make_url(raw)
    if url.drivername == "postgresql":
        url = url.set(drivername="postgresql+psycopg")

    if not (url.drivername.startswith("sqlite") or url.drivername.startswith("postgresql")):
        raise ValueError(
            "unsupported reporting database dialect: "
            f"{url.drivername}; use PostgreSQL or SQLite"
        )
    return url.render_as_string(hide_password=False)


def resolve_reporting_database_url(
    project_root: Path,
    environ: Mapping[str, str] | None = None,
) -> str:
    """Resolve the reporting database from environment, with a local SQLite fallback.

    PostgreSQL is the intended production/deployed backend. The SQLite fallback keeps
    unit tests and the lightweight local demo workflow self-contained.
    """
    env = os.environ if environ is None else environ
    configured = env.get(REPORTING_DATABASE_ENV, "").strip()
    if configured:
        return normalize_database_url(configured)
    return sqlite_url_for_path(project_root / "data" / "processed" / "reporting.db")


def create_reporting_engine(database_url: Path | str) -> Engine:
    """Create a SQLAlchemy engine with connection health checks enabled."""
    normalized = normalize_database_url(database_url)
    return create_engine(normalized, pool_pre_ping=True, future=True)


def database_display_name(database_url: Path | str) -> str:
    """Render a database URL without exposing a password in logs or UI messages."""
    url = make_url(normalize_database_url(database_url))
    return url.render_as_string(hide_password=True)


def sqlite_database_path(database_url: Path | str) -> Path | None:
    """Return the backing path for SQLite URLs, otherwise None."""
    url = make_url(normalize_database_url(database_url))
    if not url.drivername.startswith("sqlite") or not url.database:
        return None
    return Path(url.database)
