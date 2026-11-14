"""Tests for the delay study (src/causal.py) and the forecast (src/forecast.py).

The SQL datasets are checked on the fixture mart (expected rows by hand).
The estimators are checked on seeded synthetic data where the true effect is
known, because 5 fixture orders cannot identify a regression.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src import causal, forecast


# ----------------------------------------------------------- SQL datasets --
def test_review_dataset_on_fixture(con):
    df = causal.load_dataset(con).set_index("order_id")
    # o4 not delivered and o5 canceled are excluded
    assert list(df.index) == ["o1", "o2", "o3"]
    assert df.loc["o2", ["is_late", "is_negative", "delay_days"]].tolist() == [1.0, 1.0, 5]
    assert df.loc["o1", "seller_key"] == "s1"            # highest-price line (100 vs 50)
    assert df.loc["o1", "multi_seller"] == 1.0
    assert df.loc["o3", ["customer_state", "seller_state", "same_state"]].tolist() == ["BA", "MG", 0.0]
    assert df.loc["o2", "delay_bucket"] == "late 4-7 days"


def test_weekly_orders_on_fixture(con):
    s = con.execute(forecast.WEEKLY_SQL.read_text()).df()
    # o2 bought on Sunday 2017-02-05 belongs to the ISO week starting Monday 2017-01-30
    assert s["week_start"].astype(str).tolist() == ["2017-01-09", "2017-01-30", "2017-02-06", "2017-02-20"]
    assert s["orders"].sum() == 4                         # canceled o5 excluded


def test_delay_buckets_boundaries():
    got = causal.delay_bucket(pd.Series([-9, -8, -7, 0, 1, 3, 4, 7, 8, 14, 15]))
    assert got.tolist() == ["early 8+ days", "early 8+ days", "on time (0-7 days early)",
                            "on time (0-7 days early)", "late 1-3 days", "late 1-3 days",
                            "late 4-7 days", "late 4-7 days", "late 8-14 days",
                            "late 8-14 days", "late 15+ days"]


# ------------------------------------------------------- causal estimators --
def synthetic_orders(n: int = 6000, true_effect: float = -1.5, seed: int = 0) -> pd.DataFrame:
    """Orders where bad sellers are both more often late and lower-rated.

    The raw late/on-time gap is therefore more negative than ``true_effect``;
    a within-seller comparison should recover it.
    """
    rng = np.random.default_rng(seed)
    n_sellers = 60
    seller = rng.integers(0, n_sellers, n)
    quality = np.linspace(-1, 1, n_sellers)[seller]          # seller quality
    p_late = 1 / (1 + np.exp(2.5 + 1.5 * quality))            # bad sellers are late more often
    late = (rng.random(n) < p_late).astype(float)
    score = 4 + 0.6 * quality + true_effect * late + rng.normal(0, 0.5, n)
    states = np.array(["SP", "RJ", "BA"])
    return pd.DataFrame({
        "order_id": [f"o{i}" for i in range(n)],
        "seller_key": [f"s{s}" for s in seller],
        "is_late": late, "review_score": score,
        "is_negative": (score <= 2.5).astype(float),
        "items_value": rng.gamma(2, 60, n), "promised_days": rng.integers(7, 40, n).astype(float),
        "log_items_value": 0.0, "log_freight": rng.normal(3, 0.3, n),
        "items_count": 1.0, "multi_seller": 0.0, "installments": 1.0,
        "same_state": rng.integers(0, 2, n).astype(float),
        "payment_type": "credit_card", "customer_state": states[rng.integers(0, 3, n)],
        "seller_state": states[seller % 3], "category": "cat",
        "purchase_month": rng.choice(["2017-03", "2017-04"], n),
    })


def test_seller_fixed_effects_remove_seller_confounding():
    df = synthetic_orders()
    raw = causal.raw_difference(df, "review_score").effect
    fe = causal.seller_fixed_effects(df, "review_score")
    assert raw < -1.6                                          # biased by seller quality
    assert fe.effect == pytest.approx(-1.5, abs=0.06)
    assert fe.ci95[0] < -1.5 < fe.ci95[1]


def test_cem_weights_balance_strata():
    df = synthetic_orders(n=3000, seed=1)
    w, match_rate = causal.cem_weights(df)
    assert 0 < match_rate <= 1
    treated = df["is_late"] == 1
    assert set(w[treated].unique()) <= {0.0, 1.0}
    # matched controls are re-weighted to the treated count in each stratum
    strata = causal.cem_strata(df)
    s = pd.DataFrame({"s": strata, "t": treated, "w": w})
    by = s[s.w > 0].groupby(["s", "t"])["w"].sum().unstack()
    ratio = by[False] / by[True]
    assert np.allclose(ratio, ratio.iloc[0])


# ---------------------------------------------------------------- forecast --
def test_simple_forecasters():
    y = np.array([10.0, 12.0, 14.0, 16.0, 18.0])
    assert forecast.naive(y, 2).tolist() == [18.0, 18.0]
    assert forecast.mean_4w(y, 1).tolist() == [15.0]
    assert forecast.drift(y, 2).tolist() == [20.0, 22.0]


def test_backtest_uses_only_past_data_and_scores():
    idx = pd.date_range("2020-01-06", periods=40, freq="W-MON")
    rng = np.random.default_rng(3)
    series = pd.Series(1000 + rng.normal(0, 50, 40), index=idx)
    models = {"naive": forecast.naive, "mean_4w": forecast.mean_4w}
    bt = forecast.backtest(series, models, horizon=3, n_origins=10)
    assert len(bt) == 2 * 10 * 3
    assert (bt["origin"] < bt["target_week"]).all()
    assert bt["target_week"].max() == idx[-1]
    # naive forecast at each origin equals the last value before it
    first = bt[(bt.model == "naive") & (bt.h == 1)].iloc[0]
    assert first["forecast"] == pytest.approx(series[first["origin"]])
    scores = forecast.score(bt).set_index("model")
    assert scores.loc["naive", "mae_vs_naive"] == 1.0
    # on white noise around a constant, averaging beats carrying the last value
    assert scores.loc["mean_4w", "mae"] < scores.loc["naive", "mae"]


def test_forward_forecast_interval_contains_point():
    idx = pd.date_range("2020-01-06", periods=40, freq="W-MON")
    series = pd.Series(1000 + np.random.default_rng(4).normal(0, 50, 40), index=idx)
    bt = forecast.backtest(series, {"mean_4w": forecast.mean_4w}, horizon=4, n_origins=12)
    fwd = forecast.forward_forecast(series, bt, "mean_4w")
    assert len(fwd) == 4 and fwd["week_start"].iloc[0] == idx[-1] + pd.Timedelta(weeks=1)
    assert ((fwd["pi_low"] <= fwd["forecast"]) & (fwd["forecast"] <= fwd["pi_high"])).all()
