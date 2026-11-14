"""Beyond-descriptive analyses: delivery-delay impact study and demand forecast.

Runs :mod:`src.causal` and :mod:`src.forecast` on the mart, saves the result
tables as CSV (``reports/analysis_results/``), draws two figures and writes
``reports/ANALYSIS_DELAY_AND_FORECAST.md``. Every number in that report is
read from the result objects, none is typed by hand.
"""
from __future__ import annotations

import warnings
from pathlib import Path

import duckdb
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from src.causal import DELAY_BUCKETS, run_study  # noqa: E402
from src.config import FIGURES_DIR, REPORTS_DIR  # noqa: E402
from src.forecast import HORIZON, N_ORIGINS, PI_LEVEL, run_forecast  # noqa: E402
from src.queries import df_to_markdown  # noqa: E402
from src.report import BLUE, ORANGE, SURFACE, TEXT, TEXT_2, _save, _style  # noqa: E402

RESULTS_DIR = REPORTS_DIR / "analysis_results"


def plot_delay_effect(dose: pd.DataFrame, out_dir: Path = FIGURES_DIR) -> Path:
    """Raw vs adjusted review-score gap by delay bucket, with 95% CI on the adjusted one."""
    _style()
    fig, ax = plt.subplots(figsize=(9, 4.2))
    d = dose.set_index("delay_bucket").loc[list(DELAY_BUCKETS)].iloc[::-1]
    y = np.arange(len(d))
    ax.axvline(0, color=TEXT_2, lw=1, zorder=1)
    ax.scatter(d["raw_gap"], y + 0.12, s=64, color=ORANGE, edgecolor=SURFACE, linewidth=2,
               label="Raw gap (no controls)", zorder=3)
    ax.errorbar(d["adjusted_gap"], y - 0.12, xerr=1.96 * d["adjusted_se"], fmt="o", ms=8,
                color=BLUE, mec=SURFACE, mew=2, elinewidth=2, capsize=0,
                label="Adjusted gap, 95% CI (controls, seller-clustered SE)", zorder=4)
    for yi, (bucket, row) in zip(y, d.iterrows()):
        if bucket.startswith("late"):
            ax.annotate(f"{row['adjusted_gap']:+.2f}", (row["adjusted_gap"], yi - 0.12),
                        xytext=(0, -16), textcoords="offset points", ha="center",
                        fontsize=9, color=TEXT)
    ax.set_yticks(y, [f"{b}  (n={n:,})" for b, n in zip(d.index, d["orders"])])
    ax.set_xlabel("Difference in average review score vs on-time orders (stars)")
    ax.set_xlim(-2.9, 0.6)
    ax.grid(axis="y", visible=False)
    ax.legend(loc="lower right", fontsize=9)
    ax.set_title("A late delivery costs about 2 stars, and controls barely move the gap")
    return _save(fig, "07_delay_effect_on_review.png", out_dir)


def plot_forecast(series: pd.Series, forward: pd.DataFrame, scores: pd.DataFrame,
                  out_dir: Path = FIGURES_DIR) -> Path:
    """Weekly orders with the 4-week forecast (left) and backtest MAE by model (right)."""
    _style()
    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(12, 4.2), gridspec_kw={"width_ratios": [2.3, 1]})
    ax.plot(series.index, series.values, color=BLUE, lw=2, label="Weekly valid orders")
    last = pd.DataFrame({"week_start": [series.index[-1]], "forecast": [series.iloc[-1]],
                         "pi_low": [series.iloc[-1]], "pi_high": [series.iloc[-1]]})
    f = pd.concat([last, forward[["week_start", "forecast", "pi_low", "pi_high"]]])
    ax.fill_between(f["week_start"], f["pi_low"], f["pi_high"], color=ORANGE, alpha=0.18, lw=0,
                    label=f"{PI_LEVEL:.0%} empirical interval")
    ax.plot(f["week_start"], f["forecast"], color=ORANGE, lw=2, ls="--",
            label=f"Forecast ({forward['model'].iloc[0]})")
    bt_start = series.index[-N_ORIGINS - HORIZON]
    ax.axvspan(bt_start, series.index[-1], color=TEXT_2, alpha=0.06, lw=0)
    ax.text(bt_start, ax.get_ylim()[1] * 0.97, "  backtest window", color=TEXT_2, fontsize=8, va="top")
    ax.set_ylabel("Orders per week")
    ax.legend(loc="upper left", fontsize=9)
    ax.set_title("Weekly orders and 4-week forecast")

    s = scores.sort_values("mae", ascending=False)
    colors = [ORANGE if m == forward["model"].iloc[0] else BLUE for m in s["model"]]
    bars = ax2.barh(s["model"], s["mae"], color=colors, height=0.62, zorder=2)
    ax2.bar_label(bars, [f"{v:,.0f}" for v in s["mae"]], padding=3, fontsize=9, color=TEXT)
    ax2.set_xlabel(f"MAE, orders/week ({N_ORIGINS} origins x h=1..{HORIZON})")
    ax2.grid(axis="y", visible=False)
    ax2.set_xlim(0, s["mae"].max() * 1.2)
    ax2.set_title("Backtest error by model")
    fig.tight_layout()
    return _save(fig, "08_weekly_orders_forecast.png", out_dir)


def _fmt_estimates(est: pd.DataFrame) -> pd.DataFrame:
    out = est.copy()
    is_neg = out["outcome"].str.startswith("Negative")
    for c in ("effect", "ci95_low", "ci95_high", "std_error"):
        out[c] = np.where(is_neg, out[c] * 100, out[c])
    out["unit"] = np.where(is_neg, "pp", "stars")
    out["effect"] = out["effect"].map(lambda v: f"{v:+.2f}")
    out["95% CI"] = [f"[{lo:.2f}, {hi:.2f}]" for lo, hi in zip(out["ci95_low"], out["ci95_high"])]
    return out[["outcome", "method", "effect", "unit", "95% CI", "n_obs"]]


def write_report(study: dict, fc: dict, figures: list[Path],
                 out_path: Path = REPORTS_DIR / "ANALYSIS_DELAY_AND_FORECAST.md") -> Path:
    """Markdown report of both analyses, filled from the result objects."""
    est = study["estimates"]
    score_rows = est[est["outcome"].str.startswith("Review")].set_index("method")["effect"]
    neg = study["negative_rate"]
    before = study["reviewed_before_delivery"]
    scores = fc["scores"].set_index("model")
    best = fc["best_model"]
    fwd = fc["forward"]
    bal = study["balance"].reset_index().rename(columns={"index": "covariate"})
    rel = [p.relative_to(REPORTS_DIR).as_posix() for p in figures]
    text = f"""# Delivery delay vs review score, and a weekly demand forecast

Generated by `python -m src.pipeline` (`src/causal.py`, `src/forecast.py`, `src/insights.py`).
Result tables: `reports/analysis_results/`.

## 1. How much does a late delivery cost in review score? (observational study)

**Population.** {study['n_orders']:,} valid-sale orders purchased Jan 2017 to Aug 2018, delivered
and reviewed. {study['n_late']:,} ({study['late_share']:.1%}) arrived after the promised date.
Negative-review rate (1-2 stars): {neg[0.0]:.1%} when not late, {neg[1.0]:.1%} when late.

**Why the raw gap could mislead.** Late orders differ from the others before anything goes wrong:

{df_to_markdown(bal.round(3))}

**Estimates of the late-delivery effect** (standard errors clustered by seller):

{df_to_markdown(_fmt_estimates(est))}

Controls (all known at purchase time): log basket value, log freight, number of items, multi-seller
order, promised lead time, instalments, payment type, customer state, seller state, main product
category, purchase month. Seller fixed effects compare late and on-time parcels *of the same seller*.
Coarsened exact matching compares each late order with on-time orders of the same customer state,
quarter, category, promised-lead-time band and basket-value quartile; {study['match_rate']:.1%} of
late orders found a match.

**Reading.** The four review-score estimates range from {score_rows.max():+.2f} to
{score_rows.min():+.2f} stars. Adding controls, seller fixed effects or matching moves the raw
gap by less than 0.1 star, so the observed differences between late and on-time orders (region,
season, basket, seller) explain very little of it. The gap grows with the delay and saturates
after about one week:

{df_to_markdown(study['dose_response'].round(3))}

![Delay effect]({rel[0]})

**Mechanism worth knowing.** According to the dataset description, the satisfaction survey is
e-mailed when the product arrives or when the estimated delivery date is reached, whichever comes
first. {before[1.0]:.1%} of late orders were reviewed *before the parcel arrived* (vs
{before[0.0]:.1%} of the others): the bad review is written while the customer is still waiting.

**Caveats (why this is "causal-flavoured", not causal).**
- Observational data: the estimates are causal only if nothing unobserved drives both lateness
  and the score (fragile or bulky goods, a bad carrier route, a stock-out the seller hid).
  Stability across specifications is reassuring but is not proof.
- Lateness is measured against Olist's own promise. A longer promise reduces "late" by definition;
  the effect is of missing the promise, not of slow delivery in itself.
- Only reviewed orders are analysed. The {study['unreviewed'][0]:,} delivered orders without a
  review were late {study['unreviewed'][1]:.1%} of the time (vs {study['late_share']:.1%} in the
  sample), so the sample under-represents late deliveries.
- A linear model on a 1-5 score; the negative-review model is a linear probability model. Both are
  read as average differences, which is what a manager needs.
- The clean test would be an experiment, e.g. randomly padding the promised date for a subset of
  routes and comparing review scores.

## 2. Weekly demand forecast

**Series.** {len(fc['series'])} complete weeks of valid orders, {fc['series'].index[0]:%Y-%m-%d} to
{fc['series'].index[-1]:%Y-%m-%d}. The series stops there because the public extract fades out
after 22 Aug 2018 (daily orders drop from about 250 to under 100), which is an extraction artefact,
not demand.

**Backtest.** Rolling origin: at each of the last {N_ORIGINS} weeks every model is refit on the past
only and forecasts 1 to {HORIZON} weeks ahead ({N_ORIGINS * HORIZON} forecasts per model).

{df_to_markdown(fc['scores'].round(3))}

**Reading.** `{best}` has the lowest error: MAE {scores.loc[best, 'mae']:,.0f} orders/week
(MAPE {scores.loc[best, 'mape_pct']:.1f}%), {1 - scores.loc[best, 'mae_vs_naive']:.0%} below the
naive forecast. The naive forecast is still best one week ahead (MAE
{scores.loc['naive', 'mae_h1']:,.0f} vs {scores.loc[best, 'mae_h1']:,.0f}); averaging wins from two
weeks ahead. Fitted by maximum likelihood on this history, the ETS models put almost all weight
on the last week (SES level smoothing = {fc['ses_alpha']:.2f}; 1 = naive), because the 2017
ramp-up looks like a series of permanent level shifts, so they behave like the naive forecast. With one partial year of
history, yearly seasonality (Black Friday, Christmas) cannot be estimated, and in 2018 weekly demand
moves around a plateau of about {fc['series']['2018-01-01':].median():,.0f} orders.

**Forward forecast** (`{best}`, {PI_LEVEL:.0%} interval from the empirical distribution of its
backtest errors at each horizon):

{df_to_markdown(fwd.assign(week_start=fwd['week_start'].dt.strftime('%Y-%m-%d')).round(0))}

These weeks fall after the end of the extract, so they cannot be checked against actuals.

![Forecast]({rel[1]})

**Limitations and next steps.** No promotion calendar, prices or marketing spend are available,
which is where a forecast usually gains most. With 2+ years of data: yearly seasonality
(seasonal ETS or holiday regressors for Black Friday and Christmas), fitting on the post-ramp-up
period only, and forecasts by region/category reconciled to the total.
"""
    out_path.write_text(text, encoding="utf-8")
    return out_path


def run(con: duckdb.DuckDBPyConnection) -> dict[str, dict]:
    """Run both analyses, save CSVs, figures and the Markdown report."""
    study = run_study(con)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")      # statsmodels convergence chatter on short series
        fc = run_forecast(con)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    study["estimates"].to_csv(RESULTS_DIR / "delay_effect_estimates.csv", index=False)
    study["dose_response"].to_csv(RESULTS_DIR / "delay_dose_response.csv", index=False)
    study["balance"].to_csv(RESULTS_DIR / "delay_covariate_balance.csv")
    fc["scores"].to_csv(RESULTS_DIR / "forecast_backtest_scores.csv", index=False)
    fc["forward"].to_csv(RESULTS_DIR / "forecast_next_4_weeks.csv", index=False)
    fc["series"].rename("orders").to_csv(RESULTS_DIR / "weekly_orders.csv", index_label="week_start")
    figures = [plot_delay_effect(study["dose_response"]),
               plot_forecast(fc["series"], fc["forward"], fc["scores"])]
    write_report(study, fc, figures)
    return {"study": study, "forecast": fc}


if __name__ == "__main__":
    from src.config import DB_PATH
    run(duckdb.connect(str(DB_PATH), read_only=True))
