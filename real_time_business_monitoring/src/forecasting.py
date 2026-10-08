"""Lightweight forecasting: seasonal (hour-of-day) median profile x recent level."""
import numpy as np
import pandas as pd

MIN_HOURS_FOR_FORECAST = 48
BACKTEST_HOURS = 24
METHOD_TEXT = ("Seasonal profile (median by hour of day) x level adjustment "
               "(last 24 hours vs profile, limited to 0.5-1.5)")


def _complete_hours(hourly: pd.DataFrame, data_now) -> pd.DataFrame:
    """Keep only finished hours (the current hour is still incomplete) and fill gaps with 0."""
    if hourly is None or hourly.empty:
        return pd.DataFrame(columns=["revenue", "transactions"], dtype=float)
    cutoff = pd.Timestamp(data_now).floor("h")
    done = hourly[hourly.index < cutoff]
    if done.empty:
        return done
    full_index = pd.date_range(done.index.min(), done.index.max(), freq="h")
    return done.reindex(full_index, fill_value=0)


def _seasonal_forecast(history: pd.Series, horizon: int) -> pd.Series:
    profile = history.groupby(history.index.hour).median()
    last_day = history.iloc[-24:]
    expected = profile.reindex(last_day.index.hour).to_numpy()
    expected_sum = float(np.nansum(expected))
    level = 1.0 if expected_sum <= 0 else float(np.clip(last_day.sum() / expected_sum, 0.5, 1.5))

    future_index = pd.date_range(history.index[-1] + pd.Timedelta(hours=1), periods=horizon, freq="h")
    base = profile.reindex(future_index.hour).fillna(profile.mean())
    values = np.clip(base.to_numpy() * level, 0, None)
    return pd.Series(values, index=future_index)


def _backtest(df: pd.DataFrame):
    if len(df) < MIN_HOURS_FOR_FORECAST + BACKTEST_HOURS:
        return {}, []
    train, test = df.iloc[:-BACKTEST_HOURS], df.iloc[-BACKTEST_HOURS:]
    metrics, preds = {}, {}
    for col in ["revenue", "transactions"]:
        pred = _seasonal_forecast(train[col], BACKTEST_HOURS)
        actual = test[col]
        abs_err = np.abs(pred.to_numpy() - actual.to_numpy())
        total_actual = float(actual.sum())
        metrics[f"{col}_mae"] = float(abs_err.mean())
        metrics[f"{col}_wape_pct"] = float(100 * abs_err.sum() / total_actual) if total_actual > 0 else None
        preds[col] = pred
    metrics["backtest_hours"] = float(BACKTEST_HOURS)
    rows = [{
        "hour": ts.to_pydatetime(),
        "actual_revenue": float(test.loc[ts, "revenue"]),
        "forecast_revenue": float(preds["revenue"].loc[ts]),
        "actual_transactions": float(test.loc[ts, "transactions"]),
        "forecast_transactions": float(preds["transactions"].loc[ts]),
    } for ts in test.index]
    return metrics, rows


def build_forecast(hourly: pd.DataFrame, data_now, horizon: int = 12) -> dict:
    df = _complete_hours(hourly, data_now)
    if len(df) < MIN_HOURS_FOR_FORECAST:
        return {"status": "insufficient_data",
                "message": f"Need at least {MIN_HOURS_FOR_FORECAST} complete hours; have {len(df)}.",
                "method": METHOD_TEXT, "metrics": {}, "actual": [], "backtest": [], "forecast": []}

    rev = _seasonal_forecast(df["revenue"], horizon)
    txn = _seasonal_forecast(df["transactions"], horizon)
    forecast = [{"hour": ts.to_pydatetime(), "revenue": float(r), "transactions": float(t)}
                for ts, r, t in zip(rev.index, rev.to_numpy(), txn.to_numpy())]
    actual = [{"hour": ts.to_pydatetime(), "revenue": float(row.revenue),
               "transactions": float(row.transactions)}
              for ts, row in df.iloc[-48:].iterrows()]
    metrics, backtest = _backtest(df)
    return {"status": "ok", "message": "", "method": METHOD_TEXT, "metrics": metrics,
            "actual": actual, "backtest": backtest, "forecast": forecast}