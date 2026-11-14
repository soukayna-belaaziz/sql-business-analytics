"""Data-quality results from the dbt tests (``olist_dbt/models/**/_*.yml``).

Every dbt test returns the failing rows. Tests with ``severity: warn`` encode
known source issues (reported and monitored, not fatal); every other test is
an error and stops ``dbt build``. This module turns dbt's ``run_results.json``
and ``manifest.json`` into one tidy table for the report and the tests.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.config import DBT_TARGET_DIR, RAW_DIR
from src.dbt_runner import DbtError, load_artifact, run_dbt

# Category shown in the report when a test does not set meta.category.
_DEFAULT_CATEGORY = {
    "unique": "duplicates",
    "unique_combination": "duplicates",
    "not_null": "nulls",
    "relationships": "referential_integrity",
    "accepted_values": "validity",
    "expression_is_true": "validity",
    "equal_row_count": "reconciliation",
}
_STATUS = {"pass": "PASS", "warn": "WARN", "fail": "FAIL", "error": "FAIL", "skipped": "SKIP"}


class DataQualityError(RuntimeError):
    """Raised when at least one error-level test fails."""


def collect_test_results(target_dir: Path = DBT_TARGET_DIR) -> pd.DataFrame:
    """One row per dbt test of the last run: name, model, category, severity, failing rows, status."""
    manifest = load_artifact("manifest", target_dir)
    rows = []
    for r in load_artifact("run_results", target_dir)["results"]:
        node = manifest["nodes"].get(r["unique_id"], {})
        if node.get("resource_type") != "test":
            continue
        test_type = (node.get("test_metadata") or {}).get("name", "singular")
        attached = [d.split(".")[-1] for d in node.get("depends_on", {}).get("nodes", [])]
        rows.append({
            "check_name": node["name"],
            "model": attached[0] if len(attached) == 1 else ", ".join(attached),
            "test_type": test_type,
            "category": node["config"].get("meta", {}).get(
                "category", _DEFAULT_CATEGORY.get(test_type, "other")),
            "severity": node["config"]["severity"].lower(),
            "failing_rows": int(r.get("failures") or 0),
            "status": _STATUS.get(r["status"], r["status"].upper()),
        })
    df = pd.DataFrame(rows)
    order = {"FAIL": 0, "WARN": 1, "PASS": 2, "SKIP": 3}
    return (df.assign(_o=df["status"].map(order))
              .sort_values(["_o", "severity", "category", "check_name"])
              .drop(columns="_o").reset_index(drop=True))


def run_tests(db_path: Path, raw_dir: Path = RAW_DIR,
              target_dir: Path = DBT_TARGET_DIR) -> pd.DataFrame:
    """Run ``dbt test`` on an existing database and return the results table.

    Failing error-level tests do not raise here (use :func:`assert_no_errors`).
    """
    try:
        run_dbt(["test"], raw_dir, db_path, target_dir)
    except DbtError:
        pass
    return collect_test_results(target_dir)


def assert_no_errors(results: pd.DataFrame) -> None:
    """Raise :class:`DataQualityError` if any error-level test failed."""
    failed = results[results["status"] == "FAIL"]
    if not failed.empty:
        raise DataQualityError(
            "Data-quality errors:\n" + failed[["check_name", "failing_rows"]].to_string(index=False))


def to_markdown(results: pd.DataFrame) -> str:
    """Render the test results as a Markdown table."""
    lines = ["| Test | Model | Category | Severity | Failing rows | Status |",
             "|---|---|---|---|---:|---|"]
    for r in results.itertuples(index=False):
        lines.append(f"| {r.check_name} | {r.model} | {r.category} | {r.severity} | "
                     f"{r.failing_rows:,} | {r.status} |")
    return "\n".join(lines) + "\n"
