"""Build the DuckDB database: staging -> clean -> mart.

The SQL lives in ``sql/``; this module only reads the files, substitutes the
raw-data folder and executes them in order.
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path

import duckdb

from src.config import DB_PATH, ETL_SCRIPTS, MART_TABLES, RAW_DIR


def render_sql(path: Path, raw_dir: Path) -> str:
    """Return the SQL text of ``path`` with ``{raw_dir}`` filled in."""
    text = path.read_text(encoding="utf-8")
    return text.replace("{raw_dir}", raw_dir.resolve().as_posix())


def build_database(
    raw_dir: Path = RAW_DIR,
    db_path: Path | str = DB_PATH,
    scripts: tuple[Path, ...] = ETL_SCRIPTS,
) -> duckdb.DuckDBPyConnection:
    """Run the ETL scripts against ``raw_dir`` and return an open connection.

    ``db_path`` may be ``":memory:"`` (used by the tests).
    """
    if not raw_dir.exists():
        raise FileNotFoundError(
            f"{raw_dir} not found - run `python data/download_data.py` first")
    if db_path != ":memory:":
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        Path(db_path).unlink(missing_ok=True)
    con = duckdb.connect(str(db_path))
    for script in scripts:
        con.execute(render_sql(script, raw_dir))
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
