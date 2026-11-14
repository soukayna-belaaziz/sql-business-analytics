"""Interactive KPI dashboard on the Olist DuckDB mart.

Run:  streamlit run app.py   (after `python -m src.pipeline` has built data/olist.duckdb)
"""
from __future__ import annotations

import altair as alt
import duckdb
import streamlit as st

from src import dashboard as q
from src.config import DB_PATH

BLUE, ORANGE = "#2a78d6", "#eb6834"

st.set_page_config(page_title="Olist KPI dashboard", layout="wide")


@st.cache_resource
def get_connection() -> duckdb.DuckDBPyConnection:
    return duckdb.connect(str(DB_PATH), read_only=True)


con = get_connection()
months, regions, categories = q.options(con)

st.title("Olist marketplace - KPI dashboard")
st.caption("Source: Olist public e-commerce dataset, DuckDB star schema built by this repo. "
           "Revenue = item price in BRL (freight excluded), canceled/unavailable orders excluded.")

c1, c2, c3 = st.columns([2, 1.3, 1.7])
start, end = c1.select_slider("Purchase month", options=months, value=(months[0], months[-1]))
sel_regions = c2.multiselect("Customer region", regions, placeholder="All regions")
sel_cats = c3.multiselect("Product category", categories, placeholder="All categories")
f = q.Filters(start, end, tuple(sel_regions), tuple(sel_cats))

k = q.kpis(con, f)
cols = st.columns(6)
cols[0].metric("Revenue (BRL)", f"{k['revenue'] / 1e6:,.2f}M")
cols[1].metric("Orders", f"{k['orders']:,.0f}")
cols[2].metric("Avg order value (BRL)", f"{k['aov']:,.1f}")
cols[3].metric("On-time delivery", f"{100 * k['on_time_rate']:.1f}%")
cols[4].metric("Avg review score", f"{k['avg_review']:.2f}")
cols[5].metric("Repeat-order share", f"{100 * k['repeat_order_rate']:.1f}%")

left, right = st.columns(2)
with left:
    st.subheader("Monthly revenue")
    m = q.monthly(con, f)
    st.altair_chart(
        alt.Chart(m).mark_bar(color=BLUE, cornerRadiusTopLeft=3, cornerRadiusTopRight=3).encode(
            x=alt.X("year_month:O", title=None),
            y=alt.Y("revenue:Q", title="BRL", axis=alt.Axis(format="~s")),
            tooltip=["year_month", alt.Tooltip("revenue:Q", format=",.0f"), "orders"],
        ).properties(height=300),
        use_container_width=True)
with right:
    st.subheader("Top 10 categories by revenue")
    tc = q.top_categories(con, f)
    st.altair_chart(
        alt.Chart(tc).mark_bar(color=BLUE, cornerRadiusTopRight=3, cornerRadiusBottomRight=3).encode(
            x=alt.X("revenue:Q", title="BRL", axis=alt.Axis(format="~s")),
            y=alt.Y("category:N", sort="-x", title=None),
            tooltip=["category", alt.Tooltip("revenue:Q", format=",.0f"), "orders"],
        ).properties(height=300),
        use_container_width=True)

left, right = st.columns(2)
with left:
    st.subheader("On-time delivery by customer state")
    s = q.on_time_by_state(con, f, min_orders=50)
    st.altair_chart(
        alt.Chart(s).mark_bar(color=BLUE).encode(
            x=alt.X("state:N", sort="y", title=None),
            y=alt.Y("on_time_pct:Q", title="% delivered on time", scale=alt.Scale(domain=[0, 100])),
            tooltip=["state", alt.Tooltip("on_time_pct:Q", format=".1f"), "delivered_orders",
                     alt.Tooltip("avg_review:Q", format=".2f")],
        ).properties(height=280),
        use_container_width=True)
with right:
    st.subheader("Review score vs delivery promise")
    r = q.review_by_delay(con, f)
    r["delivery"] = r["delivery"].str.slice(2)
    r["late"] = r["delivery"].str.startswith("late")
    st.altair_chart(
        alt.Chart(r).mark_bar().encode(
            x=alt.X("delivery:N", sort=None, title=None, axis=alt.Axis(labelAngle=0)),
            y=alt.Y("avg_review:Q", title="Average review (1-5)", scale=alt.Scale(domain=[0, 5])),
            color=alt.Color("late:N", scale=alt.Scale(domain=[False, True], range=[BLUE, ORANGE]),
                            legend=None),
            tooltip=["delivery", "orders", alt.Tooltip("avg_review:Q", format=".2f")],
        ).properties(height=280),
        use_container_width=True)

st.caption("AOV with a category filter = revenue of the selected categories / orders containing them.")
