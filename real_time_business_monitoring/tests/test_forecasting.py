import pandas as pd

from src.forecasting import build_forecast


def test_forecast_on_clean_daily_pattern():
    hours = pd.date_range("2026-01-01", periods=24 * 10, freq="h")
    hourly = pd.DataFrame({"revenue": 1000 + 50 * hours.hour,
                           "transactions": 100 + hours.hour}, index=hours)
    data_now = hours[-1] + pd.Timedelta(minutes=30)   # last hour is still incomplete

    result = build_forecast(hourly, data_now, horizon=12)
    assert result["status"] == "ok"
    assert len(result["forecast"]) == 12
    assert result["forecast"][0]["hour"] == hours[-1].to_pydatetime()
    assert abs(result["forecast"][0]["revenue"] - (1000 + 50 * hours[-1].hour)) < 1e-6
    assert result["metrics"]["revenue_wape_pct"] < 1.0


def test_not_enough_data():
    hours = pd.date_range("2026-01-01", periods=10, freq="h")
    hourly = pd.DataFrame({"revenue": 1.0, "transactions": 1}, index=hours)
    assert build_forecast(hourly, hours[-1], 12)["status"] == "insufficient_data"