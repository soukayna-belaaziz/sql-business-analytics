"""KPI report: charts (matplotlib) and an executive summary (Markdown).

All numbers come from the analysis query results (``src.queries.run_all``) or
from the two helper queries in ``sql/report/``; nothing is typed by hand.
"""
from __future__ import annotations

from pathlib import Path

import duckdb
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402

from src.config import FIGURES_DIR, REPORTS_DIR, SQL_DIR  # noqa: E402
from src.queries import df_to_markdown  # noqa: E402

# Palette (validated categorical slots 1-2 + sequential blue ramp)
BLUE, ORANGE = "#2a78d6", "#eb6834"
TEXT, TEXT_2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3de", "#fcfcfb"
BLUE_RAMP = ["#f4f8fd", "#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]


def _style() -> None:
    plt.rcParams.update({
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
        "axes.edgecolor": GRID, "axes.labelcolor": TEXT_2, "axes.titlecolor": TEXT,
        "axes.titlesize": 12, "axes.titleweight": "bold", "axes.titlelocation": "left",
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
        "xtick.color": TEXT_2, "ytick.color": TEXT_2, "font.size": 10,
        "legend.frameon": False,
    })


def _save(fig: plt.Figure, name: str, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / name
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


def _thousands(x: float, _pos: int | None = None) -> str:
    return f"{x / 1e6:.1f}M" if abs(x) >= 1e6 else f"{x / 1e3:.0f}k"


def plot_monthly_revenue(monthly: pd.DataFrame, out_dir: Path) -> Path:
    """Monthly revenue bars with the 3-month moving average."""
    fig, ax = plt.subplots(figsize=(10, 4.2))
    x = np.arange(len(monthly))
    ax.bar(x, monthly["revenue_brl"], color=BLUE, width=0.72, label="Monthly revenue", zorder=2)
    ax.plot(x, monthly["revenue_3m_avg"], color=ORANGE, lw=2, label="3-month moving average", zorder=3)
    ax.set_xticks(x[::2], monthly["year_month"].iloc[::2], rotation=0)
    ax.yaxis.set_major_formatter(_thousands)
    ax.grid(axis="x", visible=False)
    ax.set_ylabel("BRL (item price, freight excluded)")
    peak = monthly.loc[monthly["revenue_brl"].idxmax()]
    ax.annotate(f"Black Friday month\n{peak['year_month']}: BRL {peak['revenue_brl'] / 1e6:.2f}M",
                xy=(int(monthly["revenue_brl"].idxmax()), peak["revenue_brl"]),
                xytext=(0, 8), textcoords="offset points", color=TEXT_2, fontsize=9,
                ha="center", va="bottom")
    ax.set_ylim(0, monthly["revenue_brl"].max() * 1.15)
    ax.set_title("Monthly revenue, Jan 2017 - Aug 2018")
    ax.legend(loc="upper left")
    return _save(fig, "01_monthly_revenue.png", out_dir)


def plot_cohort_heatmap(cohort_long: pd.DataFrame, out_dir: Path) -> Path:
    """Retention heatmap, months 1-12 (month 0 is 100% by definition)."""
    mat = (cohort_long[cohort_long["month_number"].between(1, 12)]
           .pivot(index="cohort", columns="month_number", values="retention_pct"))
    # cells that are not observable yet (cohort + k > 2018-08) stay NaN
    cohorts = pd.PeriodIndex(mat.index, freq="M")
    last = pd.Period("2018-08", freq="M")
    for k in mat.columns:
        mat.loc[(cohorts + k) > last, k] = np.nan
    observable = (cohorts.values[:, None] + mat.columns.values[None, :]) <= last
    mat = mat.where(~(mat.isna() & observable), 0.0)
    cmap = LinearSegmentedColormap.from_list("blue", BLUE_RAMP)
    cmap.set_bad(SURFACE)
    fig, ax = plt.subplots(figsize=(10, 6.2))
    im = ax.imshow(mat.values, cmap=cmap, aspect="auto", vmin=0, vmax=0.8)
    ax.grid(False)
    ax.set_xticks(range(mat.shape[1]), [f"M{k}" for k in mat.columns])
    ax.set_yticks(range(mat.shape[0]), mat.index)
    for i in range(mat.shape[0]):
        for j in range(mat.shape[1]):
            v = mat.values[i, j]
            if not np.isnan(v):
                ax.text(j, i, f"{v:.2f}", ha="center", va="center", fontsize=7,
                        color="white" if v > 0.5 else TEXT)
    cb = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02)
    cb.set_label("% of cohort buying again in month k", color=TEXT_2)
    cb.outline.set_visible(False)
    ax.set_xlabel("Months since first purchase")
    ax.set_title("Cohort retention: share of new customers who buy again (%)")
    return _save(fig, "02_cohort_retention.png", out_dir)


def plot_delay_vs_review(delay: pd.DataFrame, out_dir: Path) -> Path:
    """Two panels sharing the x axis: average review and % negative reviews."""
    labels = delay["delay_bucket"].str.slice(2)
    colors = [BLUE if b.startswith(("1", "2", "3", "4")) else ORANGE for b in delay["delay_bucket"]]
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
    for ax, col, title, fmt in [
        (axes[0], "avg_review", "Average review score (1-5)", "{:.2f}"),
        (axes[1], "negative_review_pct", "Share of 1-2 star reviews (%)", "{:.0f}%"),
    ]:
        bars = ax.barh(labels, delay[col], color=colors, height=0.68, zorder=2)
        ax.invert_yaxis()
        ax.grid(axis="y", visible=False)
        ax.bar_label(bars, [fmt.format(v) for v in delay[col]], padding=3, color=TEXT, fontsize=9)
        ax.set_title(title)
    axes[1].set_yticklabels([])
    axes[0].set_xlim(0, 5.2)
    axes[1].set_xlim(0, 95)
    fig.suptitle("Delivery vs promised date (blue = on time or early, orange = late)",
                 x=0.01, ha="left", color=TEXT_2, fontsize=10, y=1.0)
    fig.tight_layout()
    return _save(fig, "03_delivery_delay_vs_review.png", out_dir)


def plot_seller_pareto(curve: pd.DataFrame, out_dir: Path) -> Path:
    """Cumulative revenue share by cumulative share of sellers."""
    fig, ax = plt.subplots(figsize=(6.8, 4.6))
    ax.plot(curve["cum_sellers_pct"], curve["cum_revenue_pct"], color=BLUE, lw=2, label="Sellers")
    ax.plot([0, 100], [0, 100], color=TEXT_2, lw=1, ls="--", label="Perfect equality")
    at20 = float(np.interp(20, curve["cum_sellers_pct"], curve["cum_revenue_pct"]))
    share80 = float(curve.loc[curve["cum_revenue_pct"] >= 80, "cum_sellers_pct"].iloc[0])
    ax.scatter([20], [at20], color=BLUE, s=40, zorder=3, edgecolor=SURFACE, linewidth=2)
    ax.annotate(f"Top 20% of sellers = {at20:.1f}% of revenue", (20, at20), xytext=(24, at20 - 14),
                color=TEXT, fontsize=9)
    ax.annotate(f"80% of revenue from {share80:.1f}% of sellers", (share80, 80), xytext=(24, 60),
                color=TEXT_2, fontsize=9)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 101)
    ax.set_xlabel("Cumulative % of sellers (ranked by revenue)")
    ax.set_ylabel("Cumulative % of revenue")
    ax.set_title("Seller revenue concentration (Pareto curve)")
    ax.legend(loc="lower right")
    return _save(fig, "04_seller_pareto.png", out_dir)


def plot_rfm(rfm: pd.DataFrame, out_dir: Path) -> Path:
    """Customer share vs revenue share per RFM segment (grouped bars)."""
    labels = rfm["segment"].str.slice(2)
    y = np.arange(len(rfm))
    h = 0.38
    fig, ax = plt.subplots(figsize=(9, 4.6))
    b1 = ax.barh(y - h / 2 - 0.01, rfm["customers_pct"], h, color=BLUE, label="% of customers", zorder=2)
    b2 = ax.barh(y + h / 2 + 0.01, rfm["revenue_pct"], h, color=ORANGE, label="% of revenue", zorder=2)
    for bars in (b1, b2):
        ax.bar_label(bars, [f"{v:.1f}%" for v in bars.datavalues], padding=3, fontsize=8, color=TEXT)
    ax.set_yticks(y, labels)
    ax.invert_yaxis()
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("%")
    ax.set_title("RFM segments: share of customers vs share of revenue")
    ax.set_xlim(0, max(rfm["customers_pct"].max(), rfm["revenue_pct"].max()) * 1.15)
    ax.legend(loc="upper right")
    return _save(fig, "05_rfm_segments.png", out_dir)


def plot_regions(regions: pd.DataFrame, out_dir: Path) -> Path:
    """Small multiples of regional KPIs (one measure per panel, no dual axis)."""
    panels = [("revenue_pct", "Share of revenue (%)", "{:.1f}"),
              ("aov_brl", "Average order value (BRL)", "{:.0f}"),
              ("avg_delivery_days", "Average delivery time (days)", "{:.1f}"),
              ("on_time_pct", "On-time delivery (%)", "{:.1f}")]
    fig, axes = plt.subplots(1, 4, figsize=(13, 3.6), sharey=True)
    for ax, (col, title, fmt) in zip(axes, panels):
        bars = ax.barh(regions["region"], regions[col], color=BLUE, height=0.65, zorder=2)
        ax.bar_label(bars, [fmt.format(v) for v in regions[col]], padding=3, fontsize=8, color=TEXT)
        ax.set_title(title, fontsize=10)
        ax.grid(axis="y", visible=False)
        ax.set_xlim(0, regions[col].max() * 1.25)
    axes[0].invert_yaxis()
    fig.suptitle("Regional performance by customer macro-region", x=0.01, ha="left",
                 fontweight="bold", color=TEXT)
    fig.tight_layout()
    return _save(fig, "06_regional_performance.png", out_dir)


def build_figures(con: duckdb.DuckDBPyConnection, results: dict[str, pd.DataFrame],
                  out_dir: Path = FIGURES_DIR) -> list[Path]:
    """Create all report figures and return their paths."""
    _style()
    cohort_long = con.execute((SQL_DIR / "report" / "cohort_retention_long.sql").read_text()).df()
    curve = con.execute((SQL_DIR / "report" / "seller_pareto_curve.sql").read_text()).df()
    return [
        plot_monthly_revenue(results["01_monthly_revenue_growth"], out_dir),
        plot_cohort_heatmap(cohort_long, out_dir),
        plot_delay_vs_review(results["06_delivery_delay_vs_review"], out_dir),
        plot_seller_pareto(curve, out_dir),
        plot_rfm(results["04_rfm_segmentation"], out_dir),
        plot_regions(results["13_regional_performance"], out_dir),
    ]


def _row(df: pd.DataFrame, col: str, value: str) -> pd.Series:
    return df.loc[df[col] == value].iloc[0]


def write_executive_summary(results: dict[str, pd.DataFrame], figures: list[Path],
                            out_path: Path = REPORTS_DIR / "EXECUTIVE_SUMMARY.md") -> Path:
    """Executive summary in Markdown; every figure in the text is read from ``results``."""
    kpi = results["02_ytd_kpi_comparison"]
    monthly = results["01_monthly_revenue_growth"]
    delay = results["06_delivery_delay_vs_review"]
    pareto = results["08_seller_pareto"]
    rfm = results["04_rfm_segmentation"]
    region = results["13_regional_performance"]
    cohort = results["03_cohort_retention"]
    k = kpi.set_index("kpi")
    late = delay[delay["delay_bucket"].str.contains("late")]
    late_share = 100 * late["orders"].sum() / delay["orders"].sum()
    late_neg = late["share_of_all_negative_pct"].sum()
    top20 = float(pareto.loc[pareto["seller_decile"] == 2, "cumulative_revenue_pct"].iloc[0])
    at_risk = _row(rfm, "segment", "6 At risk, high-value")
    ne = _row(region, "region", "Northeast")
    se = _row(region, "region", "Southeast")
    m1_max = cohort["m1_pct"].max()
    last = monthly.iloc[-1]
    rel = lambda p: p.relative_to(out_path.parent).as_posix()  # noqa: E731

    kpi_tbl = kpi.rename(columns={"kpi": "KPI", "jan_aug_2017": "Jan-Aug 2017",
                                  "jan_aug_2018": "Jan-Aug 2018", "change_pct": "Change %"})
    text = f"""# Executive summary - Olist marketplace KPI report

*Generated by `python -m src.pipeline` from the DuckDB mart. Period: Jan 2017 - Aug 2018
(complete months). Revenue = item price in BRL, freight excluded; canceled/unavailable
orders excluded.*

## Headline KPIs, year to date

{df_to_markdown(kpi_tbl)}

## Five things management should know

1. **Growth is volume-driven and has plateaued.** Jan-Aug revenue is
   {k.loc['Revenue (BRL)', 'change_pct']:+.1f}% year on year, with orders
   {k.loc['Orders', 'change_pct']:+.1f}% and AOV almost flat
   ({k.loc['Average order value (BRL)', 'change_pct']:+.1f}%). Monthly revenue has moved
   sideways since March 2018; YoY growth in {last['year_month']} is {last['yoy_growth_pct']:+.1f}%.
2. **Late deliveries concentrate the bad reviews.** Late orders are {late_share:.1f}% of
   reviewed deliveries but {late_neg:.1f}% of all 1-2 star reviews. On-time delivery fell from
   {k.loc['On-time delivery %', 'jan_aug_2017']:.1f}% to {k.loc['On-time delivery %', 'jan_aug_2018']:.1f}%.
3. **Customers almost never come back.** In no cohort do more than {m1_max:.2f}% of new
   customers buy again in the following month; repeat orders are
   {k.loc['Repeat-order share %', 'jan_aug_2018']:.1f}% of 2018 orders. The
   "At risk, high-value" RFM segment holds {at_risk['revenue_pct']:.1f}% of revenue
   ({at_risk['customers']:,} customers, last purchase about {at_risk['avg_recency_days']:.0f} days ago).
4. **Seller base is highly concentrated.** The top 20% of sellers generate {top20:.1f}% of revenue.
5. **The Northeast is under-served.** It is {ne['revenue_pct']:.1f}% of revenue with the highest
   AOV among large regions (BRL {ne['aov_brl']:.0f} vs {se['aov_brl']:.0f} in the Southeast), but
   deliveries take {ne['avg_delivery_days']:.1f} days vs {se['avg_delivery_days']:.1f} and only
   {ne['on_time_pct']:.1f}% arrive on time.

## Suggested actions (to be validated with the business)

- Logistics: set a late-delivery alert per seller and customer state and review delivery-date promises in the
  Northeast; track On-time Delivery % weekly next to revenue.
- CRM: win-back campaign for the "At risk, high-value" segment; measure with a hold-out group.
- Seller management: key-account coverage for the top two revenue deciles; shipping-SLA
  enforcement for sellers who hand parcels to the carrier late (query 15).

## Charts

"""
    captions = ["Monthly revenue and 3-month moving average",
                "Cohort retention matrix (months 1-12)",
                "Delivery delay vs review score",
                "Seller Pareto curve",
                "RFM segments",
                "Regional performance"]
    for cap, fig in zip(captions, figures):
        text += f"### {cap}\n\n![{cap}]({rel(fig)})\n\n"
    text += ("Full query results: `reports/query_results/`. Query catalogue with SQL and insights: "
             "`docs/QUERIES.md`.\n")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8")
    return out_path
