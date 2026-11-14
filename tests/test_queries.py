"""Analytical query tests on the fixture (expected values computed by hand)."""
from __future__ import annotations

import pytest

from src import dashboard
from src.queries import df_to_markdown, list_queries, parse_query, run_query
from src.config import ANALYSIS_DIR


def result(con, stem: str):
    return run_query(con, parse_query(ANALYSIS_DIR / f"{stem}.sql"))


def test_every_query_has_metadata_and_runs(con):
    queries = list_queries()
    assert 12 <= len(queries) <= 15
    for q in queries:
        assert q.title and q.question and q.technique and q.insight, q.name
        run_query(con, q)  # must not raise on the fixture


def test_monthly_revenue_and_mom_growth(con):
    df = result(con, "01_monthly_revenue_growth").set_index("year_month")
    # Jan: o1 = 100 + 50 (o5 canceled excluded); Feb: o2 80 + o3 200 + o4 40
    assert df.loc["2017-01", "revenue_brl"] == 150
    assert df.loc["2017-02", "revenue_brl"] == 320
    assert df.loc["2017-02", "orders"] == 3
    assert df.loc["2017-02", "mom_growth_pct"] == pytest.approx(113.3, abs=0.05)


def test_delivery_delay_buckets(con):
    df = result(con, "06_delivery_delay_vs_review").set_index("delay_bucket")
    assert df.loc["3 early 1-7 days", "orders"] == 2          # o1 (-5), o3 (-7)
    assert df.loc["6 late 4-7 days", "avg_review"] == 1.0     # o2, latest review kept
    assert df["share_of_all_negative_pct"].sum() == pytest.approx(100.0)


def test_seller_pareto(con):
    df = result(con, "08_seller_pareto")
    # s2 = 50 + 200 = 250, s1 = 100 + 80 + 40 = 220 (canceled o5 excluded)
    assert df["revenue_brl"].tolist() == [250, 220]
    assert df["cumulative_revenue_pct"].iloc[-1] == 100.0


def test_cohort_retention(con):
    df = result(con, "03_cohort_retention").set_index("cohort")
    # Jan-2017 cohort: u1 only (u4 canceled), u1 buys again in Feb -> M1 = 100%
    assert df.loc["2017-01", "cohort_size"] == 1
    assert df.loc["2017-01", "m1_pct"] == 100.0


def test_dashboard_kpis(con):
    k = dashboard.kpis(con, dashboard.Filters())
    assert k["revenue"] == pytest.approx(470.0)
    assert k["orders"] == 4
    assert k["on_time_rate"] == pytest.approx(2 / 3)
    nordeste = dashboard.kpis(con, dashboard.Filters(regions=("Northeast",)))
    assert nordeste["revenue"] == pytest.approx(200.0)


def test_markdown_renderer():
    import pandas as pd
    md = df_to_markdown(pd.DataFrame({"a": ["x"], "b": [1234.0]}))
    assert md.splitlines()[2] == "| x | 1,234 |"
