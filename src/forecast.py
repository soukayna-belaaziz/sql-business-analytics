"""Weekly demand forecast: simple baselines vs exponential smoothing.

The planning question: "how many orders should operations expect over the
next four weeks?". With 85 weeks of history (Jan 2017 to mid-Aug 2018), one
partial seasonal cycle and a strong ramp-up, the honest benchmark is a naive
forecast. Every model is scored by rolling-origin backtesting: at each of the
last ``N_ORIGINS`` weeks the model is refit on the past only and forecasts
1 to ``HORIZON`` weeks ahead.

Models
------
* ``naive``     last observed week, carried forward
* ``mean_4w``   mean of the last 4 weeks
* ``drift``     random walk with drift (average weekly change since the start)
* ``ses``       simple exponential smoothing (ETS A,N,N) on log(orders)
* ``ets_damped`` ETS with damped additive trend (A,Ad,N) on log(orders)

The forward forecast uses the model with the lowest backtest MAE; its 80%
interval comes from the empirical distribution of that model's backtest
errors at each horizon (no distributional assumption).
"""
from __future__ import annotations

from collections.abc import Callable

import duckdb
import numpy as np
import pandas as pd
from statsmodels.tsa.exponential_smoothing.ets import ETSModel

from src.config import SQL_DIR

WEEKLY_SQL = SQL_DIR / "analytics" / "weekly_orders.sql"
HORIZON = 4
N_ORIGINS = 26
PI_LEVEL = 0.80

Forecaster = Callable[[np.ndarray, int], np.ndarray]


def load_weekly(con: duckdb.DuckDBPyConnection) -> pd.Series:
    """Weekly valid orders indexed by the Monday of the week."""
    df = con.execute(WEEKLY_SQL.read_text(encoding="utf-8")).df()
    s = df.set_index(pd.to_datetime(df["week_start"]))["orders"].astype(float)
    s.index.freq = "W-MON"
    return s


def naive(y: np.ndarray, h: int) -> np.ndarray:
    return np.repeat(y[-1], h)


def mean_4w(y: np.ndarray, h: int) -> np.ndarray:
    return np.repeat(y[-4:].mean(), h)


def drift(y: np.ndarray, h: int) -> np.ndarray:
    slope = (y[-1] - y[0]) / (len(y) - 1)
    return y[-1] + slope * np.arange(1, h + 1)


def _ets_log(y: np.ndarray, h: int, trend: str | None, damped: bool) -> np.ndarray:
    """Fit ETS on log(y) by maximum likelihood and back-transform the point forecast."""
    model = ETSModel(pd.Series(np.log(y)), error="add", trend=trend, damped_trend=damped)
    fit = model.fit(disp=False, maxiter=2000)
    return np.exp(np.asarray(fit.forecast(h)))


def ses_alpha(series: pd.Series) -> float:
    """Smoothing weight of the level estimated by SES on the whole series (1 = naive)."""
    fit = ETSModel(pd.Series(np.log(series.to_numpy())), error="add").fit(disp=False)
    return float(fit.params[0])


def ses(y: np.ndarray, h: int) -> np.ndarray:
    return _ets_log(y, h, trend=None, damped=False)


def ets_damped(y: np.ndarray, h: int) -> np.ndarray:
    return _ets_log(y, h, trend="add", damped=True)


MODELS: dict[str, Forecaster] = {
    "naive": naive, "mean_4w": mean_4w, "drift": drift, "ses": ses, "ets_damped": ets_damped,
}


def backtest(series: pd.Series, models: dict[str, Forecaster] = MODELS,
             horizon: int = HORIZON, n_origins: int = N_ORIGINS) -> pd.DataFrame:
    """Rolling-origin forecasts: one row per (model, origin, horizon step)."""
    y = series.to_numpy()
    rows = []
    first_origin = len(y) - n_origins - horizon + 1
    for origin in range(first_origin, len(y) - horizon + 1):
        train, actual = y[:origin], y[origin:origin + horizon]
        for name, fn in models.items():
            pred = fn(train, horizon)
            for step in range(horizon):
                rows.append({"model": name, "origin": series.index[origin - 1],
                             "target_week": series.index[origin + step], "h": step + 1,
                             "actual": actual[step], "forecast": float(pred[step])})
    return pd.DataFrame(rows)


def score(bt: pd.DataFrame) -> pd.DataFrame:
    """MAE, MAPE and MAE relative to the naive model, per model (all horizons)."""
    bt = bt.assign(abs_err=(bt["actual"] - bt["forecast"]).abs())
    bt["ape"] = bt["abs_err"] / bt["actual"]
    out = bt.groupby("model").agg(mae=("abs_err", "mean"), mape_pct=("ape", "mean"),
                                  bias=("forecast", "mean"))
    out["bias"] = out["bias"] - bt.groupby("model")["actual"].mean()
    out["mape_pct"] *= 100
    out["mae_vs_naive"] = out["mae"] / out.loc["naive", "mae"]
    by_h = bt.pivot_table(index="model", columns="h", values="abs_err", aggfunc="mean")
    by_h.columns = [f"mae_h{h}" for h in by_h.columns]
    return out.join(by_h).sort_values("mae").reset_index()


def forward_forecast(series: pd.Series, bt: pd.DataFrame, model: str,
                     horizon: int = HORIZON, level: float = PI_LEVEL) -> pd.DataFrame:
    """Point forecast of ``model`` after the last week, with an empirical interval.

    The interval applies the (1-level)/2 and (1+level)/2 quantiles of the
    model's backtest percentage errors at each horizon to the point forecast.
    """
    point = MODELS[model](series.to_numpy(), horizon)
    errs = bt[bt["model"] == model].assign(pct=lambda d: d["actual"] / d["forecast"] - 1)
    lo = errs.groupby("h")["pct"].quantile((1 - level) / 2).to_numpy()
    hi = errs.groupby("h")["pct"].quantile((1 + level) / 2).to_numpy()
    index = pd.date_range(series.index[-1] + pd.Timedelta(weeks=1), periods=horizon, freq="W-MON")
    return pd.DataFrame({"week_start": index, "model": model, "forecast": point,
                         "pi_low": point * (1 + lo), "pi_high": point * (1 + hi)})


def run_forecast(con: duckdb.DuckDBPyConnection) -> dict[str, object]:
    """Backtest table, scores, best model and its forward forecast."""
    series = load_weekly(con)
    bt = backtest(series)
    scores = score(bt)
    best = str(scores.iloc[0]["model"])
    return {
        "series": series,
        "backtest": bt,
        "scores": scores,
        "best_model": best,
        "ses_alpha": ses_alpha(series),
        "forward": forward_forecast(series, bt, best),
    }
