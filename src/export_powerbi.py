"""Export the mart tables as CSV files for Power BI Desktop.

The files go to ``powerbi/data/`` (git-ignored: fact_order_items alone is
about 15 MB). Load them in Power BI with Get Data > Text/CSV, see
``powerbi/POWERBI_GUIDE.md``.
"""
from __future__ import annotations

from pathlib import Path

import duckdb

from src.config import DB_PATH, MART_TABLES, POWERBI_DATA_DIR


def export_mart(con: duckdb.DuckDBPyConnection, out_dir: Path = POWERBI_DATA_DIR,
                tables: tuple[str, ...] = MART_TABLES) -> dict[str, Path]:
    """Write one CSV per mart table (header, comma separator, ISO dates)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    for table in tables:
        path = out_dir / f"{table}.csv"
        con.execute(f"COPY {table} TO '{path.as_posix()}' (HEADER, DELIMITER ',')")
        paths[table] = path
    return paths


def main() -> None:
    con = duckdb.connect(str(DB_PATH), read_only=True)
    for table, path in export_mart(con).items():
        print(f"{table:<18}{path.stat().st_size / 1e6:6.1f} MB  {path}")


if __name__ == "__main__":
    main()
