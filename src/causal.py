"""Effect of a late delivery on the review score (observational study).

Question a manager asks: "how many stars does a late delivery cost us?".
Late orders are not a random sample (they are more often long-distance,
Northeast, Black Friday and from certain sellers), so the raw gap mixes the
delay with those differences. Four estimates, from naive to most controlled:

1. raw difference in means;
2. OLS with pre-treatment controls (basket, freight, promised lead time,
   payment, customer and seller state, category, purchase month),
   standard errors clustered by seller;
3. the same plus seller fixed effects (within-seller comparison: same seller,
   on-time vs late parcels), estimated by demeaning (Frisch-Waugh-Lovell);
4. coarsened exact matching (CEM) on state x quarter x category x promised
   lead time x basket value, ATT by weighted regression.

Everything is observational: the estimates are causal only if no unobserved
factor drives both lateness and the score (e.g. a fragile product that is both
slow to ship and disappointing). The README and the memo say so.
"""
from __future__ import annotations

from dataclasses import dataclass

import duckdb
import numpy as np
import pandas as pd
import statsmodels.api as sm

from src.config import SQL_DIR

DATASET_SQL = SQL_DIR / "analytics" / "order_review_features.sql"

NUMERIC_CONTROLS: tuple[str, ...] = (
    "log_items_value", "log_freight", "items_count", "multi_seller",
    "promised_days", "installments", "same_state",
)
CATEGORICAL_CONTROLS: tuple[str, ...] = (
    "payment_type", "customer_state", "seller_state", "category", "purchase_month",
)
DELAY_BUCKETS: tuple[str, ...] = (
    "early 8+ days", "on time (0-7 days early)", "late 1-3 days",
    "late 4-7 days", "late 8-14 days", "late 15+ days",
)
REFERENCE_BUCKET = "on time (0-7 days early)"
OUTCOMES = {"review_score": "Review score (1-5)", "is_negative": "Negative review (1-2 stars)"}


@dataclass(frozen=True)
class Estimate:
    """One treatment-effect estimate."""

    outcome: str
    method: str
    effect: float
    std_error: float
    n_obs: int

    @property
    def ci95(self) -> tuple[float, float]:
        return self.effect - 1.96 * self.std_error, self.effect + 1.96 * self.std_error


def load_dataset(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Order-level analysis table with derived controls and delay bucket."""
    df = con.execute(DATASET_SQL.read_text(encoding="utf-8")).df()
    df["log_items_value"] = np.log1p(df["items_value"].astype(float))
    df["log_freight"] = np.log1p(df["freight_value"].astype(float))
    df["delay_bucket"] = delay_bucket(df["delay_days"])
    for c in ("is_late", "is_negative", "review_score", "items_count", "multi_seller",
              "promised_days", "installments", "same_state"):
        df[c] = df[c].astype(float)
    return df


def delay_bucket(delay_days: pd.Series) -> pd.Series:
    """Map delay in days (positive = late) to the labels in ``DELAY_BUCKETS``."""
    bins = [-np.inf, -8, 0, 3, 7, 14, np.inf]
    return pd.cut(delay_days, bins=bins, labels=list(DELAY_BUCKETS)).astype(str)


def design_matrix(df: pd.DataFrame, categorical: tuple[str, ...] = CATEGORICAL_CONTROLS,
                  numeric: tuple[str, ...] = NUMERIC_CONTROLS) -> pd.DataFrame:
    """Controls as a float matrix: numeric columns + dummies (first level dropped)."""
    dummies = pd.get_dummies(df[list(categorical)].astype(str), drop_first=True, dtype=float)
    return pd.concat([df[list(numeric)].astype(float), dummies], axis=1)


def _cluster_ols(y: pd.Series, X: pd.DataFrame, groups: pd.Series,
                 add_constant: bool = True, weights: pd.Series | None = None):
    """OLS / WLS with standard errors clustered on ``groups``."""
    if add_constant:
        X = sm.add_constant(X, has_constant="add")
    model = sm.OLS(y, X) if weights is None else sm.WLS(y, X, weights=weights)
    codes = pd.factorize(groups)[0]
    return model.fit(cov_type="cluster", cov_kwds={"groups": codes})


def raw_difference(df: pd.DataFrame, outcome: str) -> Estimate:
    """Unadjusted late-minus-not-late difference (OLS on the dummy, clustered SE)."""
    res = _cluster_ols(df[outcome], df[["is_late"]], df["seller_key"])
    return Estimate(outcome, "1. Raw difference", res.params["is_late"], res.bse["is_late"], len(df))


def ols_with_controls(df: pd.DataFrame, outcome: str) -> Estimate:
    """OLS of the outcome on ``is_late`` and pre-treatment controls."""
    X = pd.concat([df[["is_late"]], design_matrix(df)], axis=1)
    res = _cluster_ols(df[outcome], X, df["seller_key"])
    return Estimate(outcome, "2. OLS + controls", res.params["is_late"], res.bse["is_late"], len(df))


def seller_fixed_effects(df: pd.DataFrame, outcome: str) -> Estimate:
    """OLS with controls and seller fixed effects via within-seller demeaning.

    Sellers with a single order carry no within-seller variation and are dropped.
    ``seller_state`` is constant within seller, so it is absorbed by the effects.
    """
    df = df[df.groupby("seller_key")["order_id"].transform("size") > 1]
    cats = tuple(c for c in CATEGORICAL_CONTROLS if c != "seller_state")
    X = pd.concat([df[["is_late"]], design_matrix(df, categorical=cats)], axis=1)
    data = pd.concat([df[[outcome]], X], axis=1)
    demeaned = data - data.groupby(df["seller_key"]).transform("mean")
    Xd = demeaned.drop(columns=outcome)
    Xd = Xd.loc[:, Xd.abs().sum() > 1e-9]           # drop absorbed columns
    res = _cluster_ols(demeaned[outcome], Xd, df["seller_key"], add_constant=False)
    return Estimate(outcome, "3. OLS + controls + seller FE", res.params["is_late"],
                    res.bse["is_late"], len(df))


def cem_strata(df: pd.DataFrame) -> pd.Series:
    """Coarsened covariates -> one stratum label per order."""
    promised = pd.cut(df["promised_days"], [-np.inf, 14, 21, 28, np.inf],
                      labels=["<=14", "15-21", "22-28", ">28"]).astype(str)
    value = pd.qcut(df["items_value"].astype(float), 4,
                    labels=["q1", "q2", "q3", "q4"]).astype(str)
    quarter = pd.PeriodIndex(df["purchase_month"], freq="M").asfreq("Q").astype(str)
    return (df["customer_state"] + "|" + quarter + "|" + df["category"] + "|"
            + promised + "|" + value)


def cem_weights(df: pd.DataFrame) -> tuple[pd.Series, float]:
    """CEM weights for the ATT and the share of late orders that found a match.

    Treated orders get weight 1, controls n_t/n_c in their stratum (rescaled so
    control weights sum to the number of matched controls); unmatched strata 0.
    """
    strata = cem_strata(df)
    t = df["is_late"] == 1
    n_t = t.groupby(strata).transform("sum")
    n_c = (~t).groupby(strata).transform("sum")
    matched = (n_t > 0) & (n_c > 0)
    w = pd.Series(0.0, index=df.index)
    w[matched & t] = 1.0
    ctrl = matched & ~t
    w[ctrl] = (n_t[ctrl] / n_c[ctrl]) * (ctrl.sum() / (matched & t).sum())
    return w, float((matched & t).sum() / t.sum())


def matching_att(df: pd.DataFrame, outcome: str) -> tuple[Estimate, float]:
    """ATT from coarsened exact matching; returns the estimate and the match rate."""
    w, match_rate = cem_weights(df)
    keep = w > 0
    res = _cluster_ols(df.loc[keep, outcome], df.loc[keep, ["is_late"]],
                       df.loc[keep, "seller_key"], weights=w[keep])
    est = Estimate(outcome, "4. Coarsened exact matching (ATT)", res.params["is_late"],
                   res.bse["is_late"], int(keep.sum()))
    return est, match_rate


def dose_response(df: pd.DataFrame, outcome: str = "review_score") -> pd.DataFrame:
    """Raw and adjusted gap of each delay bucket vs on-time orders (OLS + controls)."""
    buckets = pd.get_dummies(df["delay_bucket"], dtype=float).drop(columns=REFERENCE_BUCKET)
    adj = _cluster_ols(df[outcome], pd.concat([buckets, design_matrix(df)], axis=1),
                       df["seller_key"])
    raw = _cluster_ols(df[outcome], buckets, df["seller_key"])
    ref_mean = df.loc[df["delay_bucket"] == REFERENCE_BUCKET, outcome].mean()
    rows = []
    for b in DELAY_BUCKETS:
        n = int((df["delay_bucket"] == b).sum())
        if b == REFERENCE_BUCKET:
            rows.append({"delay_bucket": b, "orders": n, "mean_outcome": ref_mean,
                         "raw_gap": 0.0, "adjusted_gap": 0.0, "adjusted_se": 0.0})
            continue
        rows.append({"delay_bucket": b, "orders": n,
                     "mean_outcome": df.loc[df["delay_bucket"] == b, outcome].mean(),
                     "raw_gap": raw.params[b], "adjusted_gap": adj.params[b],
                     "adjusted_se": adj.bse[b]})
    return pd.DataFrame(rows)


def balance_table(df: pd.DataFrame) -> pd.DataFrame:
    """Covariate means of late vs not-late orders (why the raw gap is confounded)."""
    cols = {"promised_days": "Promised lead time (days)", "items_value": "Basket value (BRL)",
            "freight_value": "Freight (BRL)", "same_state": "Seller in customer's state",
            "multi_seller": "Multi-seller order"}
    tmp = df.assign(northeast=(df["customer_region"] == "Northeast").astype(float),
                    nov_2017=(df["purchase_month"] == "2017-11").astype(float))
    cols |= {"northeast": "Customer in Northeast", "nov_2017": "Bought in Nov 2017"}
    g = tmp.groupby("is_late")[list(cols)].mean().T
    g.index = [cols[c] for c in g.index]
    g.columns = ["not late", "late"]
    return g.astype(float)


def unreviewed_late_share(con: duckdb.DuckDBPyConnection) -> tuple[int, float]:
    """Delivered valid sales (reporting period) WITHOUT a review: count and share late."""
    n, late = con.execute("""
        SELECT count(*), avg(CAST(o.delay_days > 0 AS DOUBLE))
        FROM fact_orders AS o JOIN dim_date AS d ON o.purchase_date_key = d.date_key
        WHERE o.is_valid_sale AND o.delivered_customer_ts IS NOT NULL
          AND o.review_score IS NULL AND d.is_reporting_period""").fetchone()
    return int(n), float(late or 0.0)


def run_study(con: duckdb.DuckDBPyConnection) -> dict[str, object]:
    """All estimates, the dose-response table and diagnostics."""
    df = load_dataset(con)
    estimates: list[Estimate] = []
    match_rate = float("nan")
    for outcome in OUTCOMES:
        estimates += [raw_difference(df, outcome), ols_with_controls(df, outcome),
                      seller_fixed_effects(df, outcome)]
        cem, match_rate = matching_att(df, outcome)
        estimates.append(cem)
    table = pd.DataFrame([{
        "outcome": OUTCOMES[e.outcome], "method": e.method, "effect": e.effect,
        "std_error": e.std_error, "ci95_low": e.ci95[0], "ci95_high": e.ci95[1],
        "n_obs": e.n_obs} for e in estimates])
    return {
        "data": df,
        "estimates": table,
        "dose_response": dose_response(df),
        "balance": balance_table(df),
        "match_rate": match_rate,
        "n_orders": len(df),
        "late_share": float(df["is_late"].mean()),
        "n_late": int(df["is_late"].sum()),
        "negative_rate": df.groupby("is_late")["is_negative"].mean().to_dict(),
        "unreviewed": unreviewed_late_share(con),
        "reviewed_before_delivery": df.groupby("is_late")["reviewed_before_delivery"].mean().to_dict(),
    }
