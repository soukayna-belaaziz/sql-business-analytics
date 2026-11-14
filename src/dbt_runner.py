"""Thin wrapper around dbt-core's programmatic runner (``dbtRunner``).

The ETL (staging -> clean -> mart) and its schema tests live in the dbt
project ``olist_dbt/``. This module only points dbt at a raw-data folder and a
DuckDB file, runs a command and fails loudly when dbt reports an error.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from src.config import DBT_DIR, DBT_TARGET_DIR


class DbtError(RuntimeError):
    """Raised when a dbt command does not complete successfully."""


def run_dbt(command: list[str], raw_dir: Path, db_path: Path,
            target_dir: Path = DBT_TARGET_DIR, quiet: bool = True) -> Any:
    """Run ``dbt <command>`` against ``raw_dir`` (CSV folder) and ``db_path``.

    ``target_dir`` holds manifest.json / run_results.json for this run; the
    tests use a temporary one so they never touch the real artefacts.
    Returns the ``dbtRunnerResult``; raises :class:`DbtError` on failure
    (an error-severity test failing counts as a failure).
    """
    from dbt.cli.main import dbtRunner  # imported lazily: dbt import is slow

    os.environ["OLIST_DUCKDB_PATH"] = Path(db_path).resolve().as_posix()
    args = [
        *command,
        "--project-dir", str(DBT_DIR),
        "--profiles-dir", str(DBT_DIR),
        "--target-path", str(Path(target_dir).resolve()),
        "--log-path", str((Path(target_dir) / "logs").resolve()),
        "--vars", json.dumps({"raw_dir": Path(raw_dir).resolve().as_posix()}),
    ]
    if quiet:
        args = ["--quiet", *args]
    result = dbtRunner().invoke(args)
    if not result.success:
        raise DbtError(f"dbt {' '.join(command)} failed: {result.exception or 'see run_results.json'}")
    return result


def load_artifact(name: str, target_dir: Path = DBT_TARGET_DIR) -> dict:
    """Read a dbt JSON artefact (``manifest``, ``run_results``, ``catalog``)."""
    return json.loads((Path(target_dir) / f"{name}.json").read_text(encoding="utf-8"))
