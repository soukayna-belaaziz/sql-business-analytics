"""Run the SQL data-quality checks and report them."""
from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd

from src.config import CHECKS_SQL


class DataQualityError(RuntimeError):
    """Raised when at least one check with severity 'error' fails."""


def run_checks(con: duckdb.DuckDBPyConnection, sql_path: Path = CHECKS_SQL) -> pd.DataFrame:
    """Execute the checks file; one row per check with a ``status`` column."""
    df = con.execute(sql_path.read_text(encoding="utf-8")).df()
    df["failing_rows"] = df["failing_rows"].astype("int64")
    df["status"] = "PASS"
    df.loc[(df["failing_rows"] > 0) & (df["severity"] == "warn"), "status"] = "WARN"
    df.loc[(df["failing_rows"] > 0) & (df["severity"] == "error"), "status"] = "FAIL"
    return df


def assert_no_errors(results: pd.DataFrame) -> None:
    """Raise :class:`DataQualityError` if any error-level check failed."""
    failed = results[results["status"] == "FAIL"]
    if not failed.empty:
        raise DataQualityError(
            "Data-quality errors:\n" + failed[["check_name", "failing_rows"]].to_string(index=False))


def to_markdown(results: pd.DataFrame) -> str:
    """Render the check results as a Markdown table."""
    lines = ["| Check | Category | Severity | Failing rows | Status |",
             "|---|---|---|---:|---|"]
    for r in results.itertuples(index=False):
        lines.append(f"| {r.check_name} | {r.category} | {r.severity} | "
                     f"{r.failing_rows:,} | {r.status} |")
    return "\n".join(lines) + "\n"
