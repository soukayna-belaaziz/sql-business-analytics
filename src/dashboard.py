"""Parameterised SQL used by the Streamlit dashboard (``app.py``).

Kept separate from the UI so it can be unit-tested. Every function takes the
same filters: a month range (``'YYYY-MM'``), a list of customer regions and a
list of product categories (empty list = no filter).
"""
from __future__ import annotations

from dataclasses import dataclass

import duckdb
import pandas as pd

# Item lines that pass the filters; every dashboard query starts from here.
_FILTERED_ITEMS = """
WITH items AS (
    SELECT f.*, p.category, c.region, c.state, d.year_month, d.month_start
    FROM fact_order_items AS f
    JOIN dim_product  AS p ON f.product_key = p.product_key
    JOIN dim_customer AS c ON f.customer_key = c.customer_key
    JOIN dim_date     AS d ON f.purchase_date_key = d.date_key
    WHERE f.is_valid_sale
      AND d.is_reporting_period
      AND d.year_month BETWEEN $start AND $end
      AND (len($regions) = 0 OR list_contains($regions, c.region))
      AND (len($categories) = 0 OR list_contains($categories, p.category))
), orders AS (
    SELECT o.*, any_value(i.region) AS region, any_value(i.state) AS state,
           any_value(i.year_month) AS year_month, any_value(i.month_start) AS month_start
    FROM fact_orders AS o
    JOIN items AS i USING (order_id)
    GROUP BY ALL
)
"""


@dataclass(frozen=True)
class Filters:
    """Dashboard filter state."""

    start: str = "2017-01"
    end: str = "2018-08"
    regions: tuple[str, ...] = ()
    categories: tuple[str, ...] = ()

    def params(self) -> dict[str, object]:
        return {"start": self.start, "end": self.end,
                "regions": list(self.regions), "categories": list(self.categories)}


def _q(con: duckdb.DuckDBPyConnection, body: str, f: Filters) -> pd.DataFrame:
    return con.execute(_FILTERED_ITEMS + body, f.params()).df()


def kpis(con: duckdb.DuckDBPyConnection, f: Filters) -> dict[str, float]:
    """Headline KPIs for the selection."""
    df = _q(con, """
        SELECT
            (SELECT sum(price) FROM items)                         AS revenue,
            count(*)                                               AS orders,
            count(DISTINCT customer_key)                           AS customers,
            (SELECT sum(price) FROM items) / count(*)              AS aov,
            avg(CASE WHEN is_on_time THEN 1.0 ELSE 0.0 END)
                FILTER (WHERE is_delivered)                        AS on_time_rate,
            avg(review_score)                                      AS avg_review,
            avg(CASE WHEN customer_order_seq > 1 THEN 1.0 ELSE 0.0 END) AS repeat_order_rate
        FROM orders
    """, f)
    return {k: (float(v) if pd.notna(v) else float("nan")) for k, v in df.iloc[0].items()}


def monthly(con: duckdb.DuckDBPyConnection, f: Filters) -> pd.DataFrame:
    """Revenue and orders per month."""
    return _q(con, """
        SELECT month_start, year_month, sum(price) AS revenue, count(DISTINCT order_id) AS orders
        FROM items GROUP BY ALL ORDER BY month_start
    """, f)


def top_categories(con: duckdb.DuckDBPyConnection, f: Filters, n: int = 10) -> pd.DataFrame:
    """Top-n categories by revenue."""
    return _q(con, f"""
        SELECT category, sum(price) AS revenue, count(DISTINCT order_id) AS orders
        FROM items GROUP BY category ORDER BY revenue DESC LIMIT {int(n)}
    """, f)


def on_time_by_state(con: duckdb.DuckDBPyConnection, f: Filters, min_orders: int = 100) -> pd.DataFrame:
    """On-time delivery % and review per customer state."""
    return _q(con, f"""
        SELECT state, count(*) AS delivered_orders,
               100 * avg(CASE WHEN is_on_time THEN 1.0 ELSE 0.0 END) AS on_time_pct,
               avg(review_score) AS avg_review
        FROM orders WHERE is_delivered
        GROUP BY state HAVING count(*) >= {int(min_orders)}
        ORDER BY on_time_pct
    """, f)


def review_by_delay(con: duckdb.DuckDBPyConnection, f: Filters) -> pd.DataFrame:
    """Average review by delivery delay vs the estimated date."""
    return _q(con, """
        SELECT
            CASE WHEN delay_days < 0 THEN '1 early'
                 WHEN delay_days = 0 THEN '2 on the day'
                 WHEN delay_days <= 7 THEN '3 late 1-7d'
                 ELSE '4 late 8d+' END AS delivery,
            count(*) AS orders, avg(review_score) AS avg_review
        FROM orders WHERE is_delivered AND review_score IS NOT NULL
        GROUP BY 1 ORDER BY 1
    """, f)


def options(con: duckdb.DuckDBPyConnection) -> tuple[list[str], list[str], list[str]]:
    """Available months, regions and categories for the filter widgets."""
    months = con.execute("SELECT DISTINCT year_month FROM dim_date "
                         "WHERE is_reporting_period ORDER BY 1").df()["year_month"].tolist()
    regions = con.execute("SELECT DISTINCT region FROM dim_customer ORDER BY 1").df()["region"].tolist()
    cats = con.execute("SELECT category FROM fact_order_items JOIN dim_product USING (product_key) "
                       "GROUP BY 1 ORDER BY sum(price) DESC").df()["category"].tolist()
    return months, regions, cats
