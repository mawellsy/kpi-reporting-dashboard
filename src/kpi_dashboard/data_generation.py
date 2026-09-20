from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd


DEPARTMENT_TO_REGION = {
    "Northeast": "East",
    "Southeast": "East",
    "Northwest": "West",
    "Southwest": "West",
}


@dataclass(frozen=True)
class GenerationConfig:
    start_date: str = "2026-06-01"
    days: int = 112
    seed: int = 42


class SyntheticDataGenerator:
    """Create deterministic, intentionally imperfect demo data for the KPI pipeline."""

    def __init__(self, output_dir: Path, config: GenerationConfig | None = None) -> None:
        self.output_dir = Path(output_dir)
        self.config = config or GenerationConfig()
        self.rng = np.random.default_rng(self.config.seed)
        self.dates = pd.date_range(self.config.start_date, periods=self.config.days, freq="D")
        self.departments = list(DEPARTMENT_TO_REGION)

    def generate_all(self) -> dict[str, Path]:
        self.output_dir.mkdir(parents=True, exist_ok=True)

        staffing = self._generate_staffing()
        sales = self._generate_sales(staffing)
        support = self._generate_support(sales, staffing)
        operations = self._generate_operations(staffing)

        paths = {
            "sales": self.output_dir / "sales.csv",
            "support": self.output_dir / "support_tickets.json",
            "operations": self.output_dir / "operations.db",
            "staffing": self.output_dir / "staffing.csv",
        }

        sales.to_csv(paths["sales"], index=False)
        staffing.to_csv(paths["staffing"], index=False)
        paths["support"].write_text(
            json.dumps(support.to_dict(orient="records"), indent=2, default=str),
            encoding="utf-8",
        )
        self._write_operations_db(operations, paths["operations"])
        return paths

    def _generate_staffing(self) -> pd.DataFrame:
        rows: list[dict] = []
        base_headcount = {"Northeast": 24, "Southeast": 22, "Northwest": 20, "Southwest": 18}

        for date in self.dates:
            weekday_factor = 0.88 if date.weekday() >= 5 else 1.0
            for dept in self.departments:
                headcount = max(12, base_headcount[dept] + int(self.rng.normal(0, 1.2)))
                absence_rate = 0.04
                # Inject a staffing issue that will later create visible business effects.
                if dept == "Southwest" and pd.Timestamp("2026-08-10") <= date <= pd.Timestamp("2026-08-20"):
                    absence_rate = 0.18
                absent = int(self.rng.binomial(headcount, absence_rate))
                hours = max(0.0, (headcount - absent) * 8 * weekday_factor + self.rng.normal(0, 4))
                rows.append(
                    {
                        "date": date.date().isoformat(),
                        "department": dept,
                        "region": DEPARTMENT_TO_REGION[dept],
                        "headcount": headcount,
                        "absent_count": absent,
                        "hours_worked": round(hours, 2),
                    }
                )

        df = pd.DataFrame(rows)
        # Intentional missing value for ETL validation practice.
        df.loc[df.index[17], "hours_worked"] = np.nan
        return df

    def _generate_sales(self, staffing: pd.DataFrame) -> pd.DataFrame:
        staffing_index = staffing.set_index(["date", "department"])
        rows: list[dict] = []
        opportunity_id = 1
        conversion_base = {"Northeast": 0.31, "Southeast": 0.28, "Northwest": 0.26, "Southwest": 0.24}
        ticket = 0

        for date in self.dates:
            for dept in self.departments:
                date_str = date.date().isoformat()
                absent = float(staffing_index.loc[(date_str, dept), "absent_count"])
                headcount = float(staffing_index.loc[(date_str, dept), "headcount"])
                staffing_penalty = min(0.08, (absent / max(headcount, 1)) * 0.35)
                opportunities = int(self.rng.poisson(18 if date.weekday() < 5 else 10))
                conversion_rate = max(0.08, conversion_base[dept] - staffing_penalty)

                for _ in range(opportunities):
                    converted = bool(self.rng.random() < conversion_rate)
                    segment = self.rng.choice(["SMB", "Mid-Market", "Enterprise"], p=[0.62, 0.28, 0.10])
                    mean_revenue = {"SMB": 850, "Mid-Market": 2600, "Enterprise": 7200}[segment]
                    revenue = 0.0
                    if converted:
                        revenue = max(75.0, float(self.rng.lognormal(np.log(mean_revenue), 0.45)))

                    rows.append(
                        {
                            "opportunity_id": f"OPP-{opportunity_id:06d}",
                            "created_date": date_str,
                            "department": dept,
                            "region": DEPARTMENT_TO_REGION[dept],
                            "customer_segment": segment,
                            "converted": converted,
                            "revenue": round(revenue, 2),
                        }
                    )
                    opportunity_id += 1
                    ticket += 1

        df = pd.DataFrame(rows)
        # Missing category and one extreme but possible high-value transaction.
        df.loc[df.index[31], "customer_segment"] = None
        converted_idx = df.index[df["converted"]].tolist()
        if converted_idx:
            df.loc[converted_idx[len(converted_idx) // 3], "revenue"] = 50000.0
        return df

    def _generate_support(self, sales: pd.DataFrame, staffing: pd.DataFrame) -> pd.DataFrame:
        sales_daily = sales.groupby(["created_date", "department"]).size().to_dict()
        staffing_index = staffing.set_index(["date", "department"])
        rows: list[dict] = []
        ticket_id = 1

        for date in self.dates:
            for dept in self.departments:
                date_str = date.date().isoformat()
                activity = sales_daily.get((date_str, dept), 10)
                staff = staffing_index.loc[(date_str, dept)]
                absence_ratio = float(staff["absent_count"]) / max(float(staff["headcount"]), 1)
                count = int(self.rng.poisson(max(3, activity * 0.32)))

                for _ in range(count):
                    opened_hour = int(self.rng.integers(8, 18))
                    opened_at = pd.Timestamp(date) + timedelta(hours=opened_hour, minutes=int(self.rng.integers(0, 60)))
                    unresolved = self.rng.random() < (0.09 + absence_ratio * 0.45)
                    base_hours = self.rng.gamma(shape=2.0, scale=4.5)
                    resolution_hours = base_hours * (1 + absence_ratio * 4)
                    resolved_at = None if unresolved else opened_at + timedelta(hours=float(resolution_hours))
                    satisfaction = None if unresolved else int(np.clip(round(self.rng.normal(4.25 - absence_ratio * 2, 0.65)), 1, 5))
                    rows.append(
                        {
                            "ticket_id": f"TKT-{ticket_id:06d}",
                            "opened_at": opened_at.isoformat(),
                            "resolved_at": None if resolved_at is None else resolved_at.isoformat(),
                            "department": dept,
                            "region": DEPARTMENT_TO_REGION[dept],
                            "status": "open" if unresolved else "resolved",
                            "satisfaction_score": satisfaction,
                        }
                    )
                    ticket_id += 1

        df = pd.DataFrame(rows)
        # One clearly impossible CSAT score for validation exercises.
        if len(df) > 50:
            df.loc[df.index[50], "satisfaction_score"] = 8
        return df

    def _generate_operations(self, staffing: pd.DataFrame) -> pd.DataFrame:
        staffing_index = staffing.set_index(["date", "department"])
        rows: list[dict] = []
        job_id = 1

        for date in self.dates:
            for dept in self.departments:
                date_str = date.date().isoformat()
                staff = staffing_index.loc[(date_str, dept)]
                productive_staff = max(1, int(staff["headcount"] - staff["absent_count"]))
                jobs = int(self.rng.poisson(productive_staff * (0.55 if date.weekday() < 5 else 0.30)))
                absence_ratio = float(staff["absent_count"]) / max(float(staff["headcount"]), 1)

                for _ in range(jobs):
                    target_hours = float(self.rng.uniform(2.0, 8.0))
                    delay_probability = 0.08 + absence_ratio * 0.8
                    delayed = bool(self.rng.random() < delay_probability)
                    actual_hours = target_hours * float(self.rng.uniform(0.85, 1.20))
                    if delayed:
                        actual_hours *= float(self.rng.uniform(1.25, 1.75))
                    status = "completed" if self.rng.random() > 0.04 else "open"
                    completed_date = None
                    if status == "completed":
                        completed_date = (date + timedelta(days=1 if delayed else 0)).date().isoformat()

                    rows.append(
                        {
                            "job_id": f"JOB-{job_id:06d}",
                            "scheduled_date": date_str,
                            "completed_date": completed_date,
                            "department": dept,
                            "region": DEPARTMENT_TO_REGION[dept],
                            "status": status,
                            "target_hours": round(target_hours, 2),
                            "actual_hours": round(actual_hours, 2),
                            "delayed": delayed,
                        }
                    )
                    job_id += 1

        df = pd.DataFrame(rows)
        # An impossible negative duration to verify validation catches bad source data.
        if len(df) > 25:
            df.loc[df.index[25], "actual_hours"] = -3.0
        return df

    @staticmethod
    def _write_operations_db(operations: pd.DataFrame, db_path: Path) -> None:
        if db_path.exists():
            db_path.unlink()
        with sqlite3.connect(db_path) as conn:
            operations.to_sql("operations_jobs", conn, index=False, if_exists="replace")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_operations_date ON operations_jobs(scheduled_date)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_operations_department ON operations_jobs(department)")
