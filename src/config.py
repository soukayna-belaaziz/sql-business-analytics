"""Project paths. All paths are relative to the repository root."""
from __future__ import annotations

from pathlib import Path

ROOT: Path = Path(__file__).resolve().parents[1]
RAW_DIR: Path = ROOT / "data" / "raw"
DB_PATH: Path = ROOT / "data" / "olist.duckdb"
SQL_DIR: Path = ROOT / "sql"
ETL_SCRIPTS: tuple[Path, ...] = (
    SQL_DIR / "staging" / "01_staging.sql",
    SQL_DIR / "clean" / "02_clean.sql",
    SQL_DIR / "mart" / "03_mart.sql",
)
CHECKS_SQL: Path = SQL_DIR / "checks" / "data_quality.sql"
ANALYSIS_DIR: Path = SQL_DIR / "analysis"
REPORTS_DIR: Path = ROOT / "reports"
FIGURES_DIR: Path = REPORTS_DIR / "figures"
QUERY_RESULTS_DIR: Path = REPORTS_DIR / "query_results"
POWERBI_DATA_DIR: Path = ROOT / "powerbi" / "data"

MART_TABLES: tuple[str, ...] = (
    "dim_date",
    "dim_customer",
    "dim_product",
    "dim_seller",
    "fact_orders",
    "fact_order_items",
    "fact_payments",
)
