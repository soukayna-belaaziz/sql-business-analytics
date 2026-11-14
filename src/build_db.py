"""Build the DuckDB database with dbt: seeds, staging -> clean -> mart, tests.

``dbt build`` runs models and their tests in DAG order, so a failing
error-level test stops every model downstream of it. The SQL lives in
``olist_dbt/models``; this module only calls dbt and opens the result.
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path

import duckdb

from src.config import DB_PATH, DBT_TARGET_DIR, MART_TABLES, RAW_DIR
from src.dbt_runner import run_dbt


def build_database(
    raw_dir: Path = RAW_DIR,
    db_path: Path = DB_PATH,
    target_dir: Path = DBT_TARGET_DIR,
) -> duckdb.DuckDBPyConnection:
    """Run ``dbt build`` on ``raw_dir`` into a fresh ``db_path``; return a connection."""
    if not Path(raw_dir).exists():
        raise FileNotFoundError(
            f"{raw_dir} not found - run `python data/download_data.py` first")
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db_path.unlink(missing_ok=True)
    run_dbt(["build"], raw_dir, db_path, target_dir)
    con = duckdb.connect(str(db_path))
    # dbt-duckdb may keep its in-process instance open: flush the WAL so the
    # file on disk is complete (it is copied by the tests and the dashboard).
    con.execute("CHECKPOINT")
    return con


def table_row_counts(con: duckdb.DuckDBPyConnection,
                     tables: tuple[str, ...] = MART_TABLES) -> dict[str, int]:
    """Row count of each mart table."""
    return {t: con.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in tables}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=RAW_DIR)
    parser.add_argument("--db", type=Path, default=DB_PATH)
    args = parser.parse_args()
    t0 = time.perf_counter()
    con = build_database(args.raw_dir, args.db)
    for table, n in table_row_counts(con).items():
        print(f"{table:<18}{n:>10,}")
    con.close()
    print(f"Built {args.db} in {time.perf_counter() - t0:.1f}s")


if __name__ == "__main__":
    main()
