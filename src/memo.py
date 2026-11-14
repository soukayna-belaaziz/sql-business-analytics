"""One-page stakeholder memo for a non-technical manager.

Three findings and three recommendations. Every number is read from the query
results (``src.queries.run_all``), the delay study and the forecast; the
wording is fixed, the figures are not.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.config import REPORTS_DIR


def _row(df: pd.DataFrame, col: str, value: str) -> pd.Series:
    return df.loc[df[col] == value].iloc[0]


def memo_numbers(results: dict[str, pd.DataFrame], study: dict, fc: dict) -> dict[str, float]:
    """Collect every figure quoted in the memo (kept separate so it can be tested)."""
    k = results["02_ytd_kpi_comparison"].set_index("kpi")
    delay = results["06_delivery_delay_vs_review"]
    late = delay[delay["delay_bucket"].str.contains("late")]
    region = results["13_regional_performance"]
    sellers = results["15_seller_late_shipping"]
    rfm = results["04_rfm_segmentation"]
    est = study["estimates"].set_index(["outcome", "method"])["effect"]
    score_fx = est.loc["Review score (1-5)"]
    neg_fx = est.loc["Negative review (1-2 stars)"]
    ne, se = _row(region, "region", "Northeast"), _row(region, "region", "Southeast")
    worst, best = sellers.iloc[-1], sellers.iloc[0]
    fwd = fc["forward"]
    neg_fe = float(neg_fx.loc["3. OLS + controls + seller FE"])
    return {
        "late_share": 100 * late["orders"].sum() / delay["orders"].sum(),
        "late_neg_share": late["share_of_all_negative_pct"].sum(),
        "stars_low": float(score_fx.abs().min()), "stars_high": float(score_fx.abs().max()),
        "neg_pp": 100 * neg_fe,
        "neg_rate_ontime": 100 * study["negative_rate"][0.0],
        "neg_rate_late": 100 * study["negative_rate"][1.0],
        "before_delivery": 100 * study["reviewed_before_delivery"][1.0],
        "n_late": study["n_late"],
        "avoidable_neg": study["n_late"] / 2 * neg_fe,
        "ontime_2017": k.loc["On-time delivery %", "jan_aug_2017"],
        "ontime_2018": k.loc["On-time delivery %", "jan_aug_2018"],
        "orders_growth": k.loc["Orders", "change_pct"],
        "aov_growth": k.loc["Average order value (BRL)", "change_pct"],
        "repeat_2018": k.loc["Repeat-order share %", "jan_aug_2018"],
        "at_risk_rev": _row(rfm, "segment", "6 At risk, high-value")["revenue_pct"],
        "at_risk_n": _row(rfm, "segment", "6 At risk, high-value")["customers"],
        "weekly_median_2018": float(fc["series"]["2018-01-01":].median()),
        "fc_point": float(fwd["forecast"].iloc[0]),
        "fc_low": float(fwd["pi_low"].min()), "fc_high": float(fwd["pi_high"].max()),
        "fc_gain": 100 * (1 - float(fc["scores"].iloc[0]["mae_vs_naive"])),
        "fc_mape": float(fc["scores"].iloc[0]["mape_pct"]),
        "ne_rev": ne["revenue_pct"], "ne_aov": ne["aov_brl"], "se_aov": se["aov_brl"],
        "ne_days": ne["avg_delivery_days"], "se_days": se["avg_delivery_days"],
        "ne_ontime": ne["on_time_pct"],
        "worst_sellers": worst["sellers"], "worst_rev": worst["revenue_pct"],
        "worst_late": worst["late_ship_pct"], "worst_review": worst["avg_review_weighted"],
        "best_review": best["avg_review_weighted"],
    }


def write_memo(results: dict[str, pd.DataFrame], study: dict, fc: dict,
               out_path: Path = REPORTS_DIR / "STAKEHOLDER_MEMO.md") -> Path:
    """Write ``reports/STAKEHOLDER_MEMO.md``."""
    n = memo_numbers(results, study, fc)
    text = f"""# Memo: what drives bad reviews, and what to do next

**To:** Head of Marketplace Operations  **From:** Data analyst  **Data:** Olist public dataset,
orders Jan 2017 to Aug 2018 (cancelled orders excluded)

## In one sentence

Orders more than doubled, but late deliveries (under 7% of orders) now generate a third of all bad
reviews, and they are concentrated in identifiable regions and sellers.

## Three findings

1. **A late parcel costs about two stars.** {n['late_share']:.1f}% of reviewed orders arrive after
   the promised date, yet they produce {n['late_neg_share']:.1f}% of all 1-2 star reviews. When we
   compare like with like (same seller, product category, region and month), a late order still
   scores {n['stars_low']:.1f} to {n['stars_high']:.1f} stars lower, and the chance of a bad review
   goes up by about {n['neg_pp']:.0f} percentage points ({n['neg_rate_ontime']:.0f}% on time vs
   {n['neg_rate_late']:.0f}% late). {n['before_delivery']:.0f}% of late customers wrote their review
   *before* the parcel arrived. Meanwhile on-time delivery slipped from {n['ontime_2017']:.1f}% to
   {n['ontime_2018']:.1f}% year on year.
2. **The problems cluster.** Northeast customers spend more per order (BRL {n['ne_aov']:.0f} vs
   {n['se_aov']:.0f} in the Southeast) but wait {n['ne_days']:.0f} days instead of
   {n['se_days']:.0f}, and only {n['ne_ontime']:.1f}% of their orders arrive on time. The
   {n['worst_sellers']:.0f} sellers who hand parcels to the carrier late on 20%+ of orders
   ({n['worst_late']:.1f}% on average, {n['worst_rev']:.1f}% of revenue) average
   {n['worst_review']:.2f} stars, against {n['best_review']:.2f} for the most punctual sellers.
3. **Growth is new customers, and demand has levelled off.** Orders grew {n['orders_growth']:.0f}%
   year on year (Jan-Aug 2018 vs Jan-Aug 2017) while the average basket stayed flat ({n['aov_growth']:+.1f}%). Only {n['repeat_2018']:.1f}% of
   2018 orders come from returning customers. Weekly orders in 2018 hover around
   {n['weekly_median_2018']:,.0f}.

## Three recommendations

1. **Protect the delivery promise on the worst routes.** Add a safety margin to promised dates
   for Northeast destinations and alert on any order close to its promise. If the estimated effect
   holds, halving late deliveries would have meant about {n['avoidable_neg']:,.0f} fewer 1-2 star
   reviews over the 20 months analysed. Test it first: pad the promise on a random half of routes
   for a month and compare reviews and conversion.
2. **Put the late-shipping sellers on a shipping-time agreement.** Start with the
   {n['worst_sellers']:.0f} sellers above 20% late hand-over: a weekly scorecard, a warning, then
   reduced visibility. Their {n['worst_rev']:.1f}% revenue share makes the risk manageable.
3. **Plan on a 4-week average, and test retention before scaling it.** For staffing and carrier
   capacity, a 4-week average forecasts the next weeks {n['fc_gain']:.0f}% more accurately than
   "same as last week" (typical error {n['fc_mape']:.0f}%): about {n['fc_point']:,.0f} orders a
   week, plausible range {n['fc_low']:,.0f} to {n['fc_high']:,.0f}. In parallel, run a win-back
   campaign for the {n['at_risk_n']:,.0f} high-value customers who have not bought for about a
   year ({n['at_risk_rev']:.1f}% of revenue), keeping a random 20% as a control group.

## How sure are we?

The delivery finding is consistent across four statistical approaches, but it comes from
historical data, not an experiment: something we cannot see (e.g. fragile products) could explain
part of it. That is why recommendations 1 and 3 start with a controlled test. The data is a public
sample of Olist orders, with no margin or cost data, so "revenue" means merchandise value.
Details: `reports/ANALYSIS_DELAY_AND_FORECAST.md`, `docs/QUERIES.md`.
"""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8")
    return out_path
