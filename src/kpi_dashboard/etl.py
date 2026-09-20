from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import pandas as pd

from .data_generation import DEPARTMENT_TO_REGION


EXPECTED_REGIONS = set(DEPARTMENT_TO_REGION.values())
EXPECTED_DEPARTMENTS = set(DEPARTMENT_TO_REGION)


@dataclass(frozen=True)
class ETLConfig:
    raw_dir: Path
    output_db: Path


@dataclass(frozen=True)
class ETLResult:
    run_id: str
    extracted_rows: dict[str, int]
    loaded_rows: dict[str, int]
    rejected_rows: dict[str, int]

    @property
    def total_extracted(self) -> int:
        return sum(self.extracted_rows.values())

    @property
    def total_loaded(self) -> int:
        return sum(self.loaded_rows.values())

    @property
    def total_rejected(self) -> int:
        return sum(self.rejected_rows.values())


class ETLPipeline:
    """Extract raw demo sources, validate them, and load clean rows into SQLite.

    Validation is deliberately deterministic. Rows that violate data-quality rules are
    preserved in ``etl_rejections`` rather than silently dropped or repaired.
    """

    def __init__(self, config: ETLConfig) -> None:
        self.config = config
        self.raw_dir = Path(config.raw_dir)
        self.output_db = Path(config.output_db)

    def run(self) -> ETLResult:
        run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        extracted = self.extract_all()

        transformers: dict[str, Callable[[pd.DataFrame], tuple[pd.DataFrame, pd.DataFrame]]] = {
            "sales": self.transform_sales,
            "support": self.transform_support,
            "operations": self.transform_operations,
            "staffing": self.transform_staffing,
        }

        clean: dict[str, pd.DataFrame] = {}
        rejected: dict[str, pd.DataFrame] = {}
        for source_name, frame in extracted.items():
            clean[source_name], rejected[source_name] = transformers[source_name](frame)

        self.load(clean, rejected, run_id)

        return ETLResult(
            run_id=run_id,
            extracted_rows={name: len(frame) for name, frame in extracted.items()},
            loaded_rows={name: len(frame) for name, frame in clean.items()},
            rejected_rows={name: len(frame) for name, frame in rejected.items()},
        )

    def extract_all(self) -> dict[str, pd.DataFrame]:
        return {
            "sales": self.extract_sales(),
            "support": self.extract_support(),
            "operations": self.extract_operations(),
            "staffing": self.extract_staffing(),
        }

    def extract_sales(self) -> pd.DataFrame:
        return pd.read_csv(self.raw_dir / "sales.csv")

    def extract_support(self) -> pd.DataFrame:
        records = json.loads((self.raw_dir / "support_tickets.json").read_text(encoding="utf-8"))
        return pd.DataFrame(records)

    def extract_operations(self) -> pd.DataFrame:
        source_db = self.raw_dir / "operations.db"
        with sqlite3.connect(source_db) as conn:
            return pd.read_sql_query("SELECT * FROM operations_jobs", conn)

    def extract_staffing(self) -> pd.DataFrame:
        return pd.read_csv(self.raw_dir / "staffing.csv")

    def transform_sales(self, source: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
        df = source.copy()
        issues = self._new_issue_series(df)

        required = [
            "opportunity_id",
            "created_date",
            "department",
            "region",
            "customer_segment",
            "converted",
            "revenue",
        ]
        self._require_columns(df, required, "sales")

        parsed_date = pd.to_datetime(df["created_date"], errors="coerce")
        revenue = pd.to_numeric(df["revenue"], errors="coerce")
        converted = self._coerce_bool(df["converted"])

        self._flag(issues, df["opportunity_id"].isna() | df["opportunity_id"].astype(str).str.strip().eq(""), "missing opportunity_id")
        self._flag(issues, df["opportunity_id"].duplicated(keep="first"), "duplicate opportunity_id")
        self._flag(issues, parsed_date.isna(), "invalid created_date")
        self._flag_common_org_fields(df, issues)
        self._flag(
            issues,
            ~df["customer_segment"].isin(["SMB", "Mid-Market", "Enterprise"]),
            "invalid or missing customer_segment",
        )
        self._flag(issues, converted.isna(), "invalid converted value")
        self._flag(issues, revenue.isna(), "invalid revenue")
        self._flag(issues, revenue < 0, "revenue cannot be negative")
        self._flag(issues, converted.eq(False) & revenue.fillna(0).ne(0), "unconverted opportunity must have zero revenue")
        self._flag(issues, converted.eq(True) & revenue.fillna(0).le(0), "converted opportunity must have positive revenue")

        df["created_date"] = parsed_date.dt.strftime("%Y-%m-%d")
        df["converted"] = converted.astype("boolean")
        df["revenue"] = revenue.round(2)
        return self._split(df, issues, "sales", "opportunity_id")

    def transform_support(self, source: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
        df = source.copy()
        issues = self._new_issue_series(df)

        required = [
            "ticket_id",
            "opened_at",
            "resolved_at",
            "department",
            "region",
            "status",
            "satisfaction_score",
        ]
        self._require_columns(df, required, "support")

        opened = pd.to_datetime(df["opened_at"], errors="coerce", utc=True)
        resolved = pd.to_datetime(df["resolved_at"], errors="coerce", utc=True)
        csat = pd.to_numeric(df["satisfaction_score"], errors="coerce")

        self._flag(issues, df["ticket_id"].isna() | df["ticket_id"].astype(str).str.strip().eq(""), "missing ticket_id")
        self._flag(issues, df["ticket_id"].duplicated(keep="first"), "duplicate ticket_id")
        self._flag(issues, opened.isna(), "invalid opened_at")
        self._flag_common_org_fields(df, issues)
        self._flag(issues, ~df["status"].isin(["open", "resolved"]), "invalid support status")
        self._flag(issues, df["status"].eq("resolved") & resolved.isna(), "resolved ticket requires resolved_at")
        self._flag(issues, df["status"].eq("open") & resolved.notna(), "open ticket cannot have resolved_at")
        self._flag(issues, resolved.notna() & opened.notna() & (resolved < opened), "resolved_at cannot precede opened_at")
        self._flag(issues, csat.notna() & ~csat.between(1, 5), "satisfaction_score must be between 1 and 5")

        df["opened_at"] = opened.dt.strftime("%Y-%m-%dT%H:%M:%S%z")
        df["resolved_at"] = resolved.dt.strftime("%Y-%m-%dT%H:%M:%S%z")
        df.loc[resolved.isna(), "resolved_at"] = None
        df["satisfaction_score"] = csat.astype("Int64")
        return self._split(df, issues, "support", "ticket_id")

    def transform_operations(self, source: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
        df = source.copy()
        issues = self._new_issue_series(df)

        required = [
            "job_id",
            "scheduled_date",
            "completed_date",
            "department",
            "region",
            "status",
            "target_hours",
            "actual_hours",
            "delayed",
        ]
        self._require_columns(df, required, "operations")

        scheduled = pd.to_datetime(df["scheduled_date"], errors="coerce")
        completed = pd.to_datetime(df["completed_date"], errors="coerce")
        target_hours = pd.to_numeric(df["target_hours"], errors="coerce")
        actual_hours = pd.to_numeric(df["actual_hours"], errors="coerce")
        delayed = self._coerce_bool(df["delayed"])

        self._flag(issues, df["job_id"].isna() | df["job_id"].astype(str).str.strip().eq(""), "missing job_id")
        self._flag(issues, df["job_id"].duplicated(keep="first"), "duplicate job_id")
        self._flag(issues, scheduled.isna(), "invalid scheduled_date")
        self._flag_common_org_fields(df, issues)
        self._flag(issues, ~df["status"].isin(["open", "completed"]), "invalid operations status")
        self._flag(issues, target_hours.isna() | (target_hours <= 0), "target_hours must be positive")
        self._flag(issues, actual_hours.isna() | (actual_hours < 0), "actual_hours cannot be negative")
        self._flag(issues, delayed.isna(), "invalid delayed value")
        self._flag(issues, df["status"].eq("completed") & completed.isna(), "completed job requires completed_date")
        self._flag(issues, df["status"].eq("open") & completed.notna(), "open job cannot have completed_date")
        self._flag(issues, completed.notna() & scheduled.notna() & (completed < scheduled), "completed_date cannot precede scheduled_date")

        df["scheduled_date"] = scheduled.dt.strftime("%Y-%m-%d")
        df["completed_date"] = completed.dt.strftime("%Y-%m-%d")
        df.loc[completed.isna(), "completed_date"] = None
        df["target_hours"] = target_hours.round(2)
        df["actual_hours"] = actual_hours.round(2)
        df["delayed"] = delayed.astype("boolean")
        return self._split(df, issues, "operations", "job_id")

    def transform_staffing(self, source: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
        df = source.copy()
        issues = self._new_issue_series(df)

        required = ["date", "department", "region", "headcount", "absent_count", "hours_worked"]
        self._require_columns(df, required, "staffing")

        parsed_date = pd.to_datetime(df["date"], errors="coerce")
        headcount = pd.to_numeric(df["headcount"], errors="coerce")
        absent = pd.to_numeric(df["absent_count"], errors="coerce")
        hours = pd.to_numeric(df["hours_worked"], errors="coerce")

        composite_duplicate = df.duplicated(subset=["date", "department"], keep="first")
        self._flag(issues, composite_duplicate, "duplicate date/department staffing row")
        self._flag(issues, parsed_date.isna(), "invalid staffing date")
        self._flag_common_org_fields(df, issues)
        self._flag(issues, headcount.isna() | (headcount <= 0), "headcount must be positive")
        self._flag(issues, absent.isna() | (absent < 0), "absent_count cannot be negative")
        self._flag(issues, absent > headcount, "absent_count cannot exceed headcount")
        self._flag(issues, hours.isna(), "missing or invalid hours_worked")
        self._flag(issues, hours < 0, "hours_worked cannot be negative")
        self._flag(issues, hours > (headcount * 24), "hours_worked exceeds physical maximum")

        df["date"] = parsed_date.dt.strftime("%Y-%m-%d")
        df["headcount"] = headcount.astype("Int64")
        df["absent_count"] = absent.astype("Int64")
        df["hours_worked"] = hours.round(2)
        return self._split(df, issues, "staffing", "date", record_id_builder=lambda row: f"{row['date']}|{row['department']}")

    def load(
        self,
        clean: dict[str, pd.DataFrame],
        rejected: dict[str, pd.DataFrame],
        run_id: str,
    ) -> None:
        self.output_db.parent.mkdir(parents=True, exist_ok=True)
        if self.output_db.exists():
            self.output_db.unlink()

        table_map = {
            "sales": "sales_clean",
            "support": "support_clean",
            "operations": "operations_clean",
            "staffing": "staffing_clean",
        }

        rejection_frames = [frame for frame in rejected.values() if not frame.empty]
        all_rejections = (
            pd.concat(rejection_frames, ignore_index=True)
            if rejection_frames
            else pd.DataFrame(columns=["source", "record_id", "reasons", "raw_record"])
        )
        all_rejections.insert(0, "run_id", run_id)

        run_rows = []
        for source_name in table_map:
            run_rows.append(
                {
                    "run_id": run_id,
                    "source": source_name,
                    "extracted_rows": len(clean[source_name]) + len(rejected[source_name]),
                    "loaded_rows": len(clean[source_name]),
                    "rejected_rows": len(rejected[source_name]),
                }
            )
        run_log = pd.DataFrame(run_rows)

        with sqlite3.connect(self.output_db) as conn:
            for source_name, table_name in table_map.items():
                clean[source_name].to_sql(table_name, conn, index=False, if_exists="replace")
            all_rejections.to_sql("etl_rejections", conn, index=False, if_exists="replace")
            run_log.to_sql("etl_run_source_stats", conn, index=False, if_exists="replace")
            conn.execute(
                """
                CREATE TABLE etl_runs (
                    run_id TEXT PRIMARY KEY,
                    completed_at_utc TEXT NOT NULL,
                    total_extracted INTEGER NOT NULL,
                    total_loaded INTEGER NOT NULL,
                    total_rejected INTEGER NOT NULL
                )
                """
            )
            conn.execute(
                "INSERT INTO etl_runs VALUES (?, ?, ?, ?, ?)",
                (
                    run_id,
                    datetime.now(timezone.utc).isoformat(),
                    int(run_log["extracted_rows"].sum()),
                    int(run_log["loaded_rows"].sum()),
                    int(run_log["rejected_rows"].sum()),
                ),
            )
            self._create_indexes(conn)

    @staticmethod
    def _create_indexes(conn: sqlite3.Connection) -> None:
        statements = [
            "CREATE UNIQUE INDEX idx_sales_opportunity_id ON sales_clean(opportunity_id)",
            "CREATE INDEX idx_sales_date_department ON sales_clean(created_date, department)",
            "CREATE UNIQUE INDEX idx_support_ticket_id ON support_clean(ticket_id)",
            "CREATE INDEX idx_support_department ON support_clean(department)",
            "CREATE UNIQUE INDEX idx_operations_job_id ON operations_clean(job_id)",
            "CREATE INDEX idx_operations_date_department ON operations_clean(scheduled_date, department)",
            "CREATE UNIQUE INDEX idx_staffing_date_department ON staffing_clean(date, department)",
            "CREATE INDEX idx_rejections_source ON etl_rejections(source)",
        ]
        for statement in statements:
            conn.execute(statement)

    @staticmethod
    def _require_columns(df: pd.DataFrame, columns: list[str], source_name: str) -> None:
        missing = sorted(set(columns) - set(df.columns))
        if missing:
            raise ValueError(f"{source_name} source is missing required columns: {', '.join(missing)}")

    @staticmethod
    def _new_issue_series(df: pd.DataFrame) -> pd.Series:
        return pd.Series([[] for _ in range(len(df))], index=df.index, dtype=object)

    @staticmethod
    def _flag(issues: pd.Series, mask: pd.Series, message: str) -> None:
        normalized_mask = mask.fillna(False).astype(bool)
        for idx in issues.index[normalized_mask]:
            issues.at[idx] = [*issues.at[idx], message]

    def _flag_common_org_fields(self, df: pd.DataFrame, issues: pd.Series) -> None:
        self._flag(issues, ~df["department"].isin(EXPECTED_DEPARTMENTS), "invalid department")
        self._flag(issues, ~df["region"].isin(EXPECTED_REGIONS), "invalid region")
        expected_region = df["department"].map(DEPARTMENT_TO_REGION)
        self._flag(
            issues,
            expected_region.notna() & df["region"].ne(expected_region),
            "department/region mismatch",
        )

    @staticmethod
    def _coerce_bool(series: pd.Series) -> pd.Series:
        mapping = {
            True: True,
            False: False,
            1: True,
            0: False,
            "1": True,
            "0": False,
            "true": True,
            "false": False,
            "True": True,
            "False": False,
        }
        return series.map(mapping).astype("boolean")

    @staticmethod
    def _split(
        df: pd.DataFrame,
        issues: pd.Series,
        source_name: str,
        id_column: str,
        record_id_builder: Callable[[pd.Series], str] | None = None,
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        invalid_mask = issues.map(bool)
        clean = df.loc[~invalid_mask].copy().reset_index(drop=True)

        rejection_rows = []
        for idx in df.index[invalid_mask]:
            row = df.loc[idx]
            record_id = record_id_builder(row) if record_id_builder else str(row.get(id_column, ""))
            raw_record = {
                column: (None if pd.isna(value) else value.item() if hasattr(value, "item") else value)
                for column, value in row.items()
            }
            rejection_rows.append(
                {
                    "source": source_name,
                    "record_id": record_id,
                    "reasons": json.dumps(issues.at[idx]),
                    "raw_record": json.dumps(raw_record, default=str, sort_keys=True),
                }
            )

        rejected = pd.DataFrame(
            rejection_rows,
            columns=["source", "record_id", "reasons", "raw_record"],
        )
        return clean, rejected
