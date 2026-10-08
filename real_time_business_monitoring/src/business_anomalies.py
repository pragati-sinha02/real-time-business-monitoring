"""Business-level monitoring: revenue, volume and category-level anomalies.

Expected value = MEDIAN of the same hour-of-day on earlier days (so it understands
that 3 AM is naturally quiet). This also covers the 'time-based anomaly' requirement.
"""
import pandas as pd

from . import config
from .utils import format_inr

MIN_EXPECTED_TXNS = 20
MIN_EXPECTED_CATEGORY_REVENUE = 5000
MIN_SAME_HOUR_DAYS = 3


def _expected_same_hour(series: pd.Series, ts: pd.Timestamp):
    same = series[(series.index.hour == ts.hour) & (series.index < ts.normalize())]
    if len(same) < MIN_SAME_HOUR_DAYS:
        return None
    return float(same.median())


def _alert(ts, alert_type, severity, title, message, key):
    return {"event_time": (ts + pd.Timedelta(hours=1)).to_pydatetime(),
            "alert_type": alert_type, "severity": severity, "title": title,
            "message": message, "related_key": key, "risk_score": None}


def _hour_label(ts):
    return f"{ts:%d %b %H:00}-{(ts + pd.Timedelta(hours=1)):%H:00}"


def detect_business_anomalies(hourly: pd.DataFrame, category_hourly: pd.DataFrame,
                              data_now, n_hours: int = 3) -> list:
    alerts = []
    if hourly is None or hourly.empty:
        return alerts
    cutoff = pd.Timestamp(data_now).floor("h")
    done = hourly[hourly.index < cutoff]
    if done.empty:
        return alerts
    full_index = pd.date_range(done.index.min(), done.index.max(), freq="h")
    done = done.reindex(full_index, fill_value=0)
    recent = list(done.index[-n_hours:])

    # ---- total revenue and volume ----
    for ts in recent:
        exp_rev = _expected_same_hour(done["revenue"], ts)
        exp_txn = _expected_same_hour(done["transactions"], ts)
        if exp_rev is None or exp_txn is None or exp_txn < MIN_EXPECTED_TXNS or exp_rev <= 0:
            continue
        act_rev, act_txn = float(done.loc[ts, "revenue"]), float(done.loc[ts, "transactions"])
        rev_ratio, txn_ratio = act_rev / exp_rev, act_txn / exp_txn
        key, label = ts.strftime("%Y-%m-%d %H:%M:%S"), _hour_label(ts)

        if rev_ratio < config.BIZ_LOW_RATIO:
            sev = "Critical" if rev_ratio < config.BIZ_CRITICAL_LOW_RATIO else "High"
            alerts.append(_alert(ts, "REVENUE_LOW", sev, "Revenue significantly below expected level",
                f"Revenue significantly below expected level for {label}. "
                f"Expected {format_inr(exp_rev)}, actual {format_inr(act_rev)} "
                f"({rev_ratio:.0%} of expected).", key))
        elif rev_ratio > config.BIZ_HIGH_RATIO:
            alerts.append(_alert(ts, "REVENUE_HIGH", "Medium", "Revenue significantly above expected level",
                f"Revenue well above expected level for {label}. "
                f"Expected {format_inr(exp_rev)}, actual {format_inr(act_rev)} "
                f"({rev_ratio:.0%} of expected).", key))

        if txn_ratio < config.BIZ_LOW_RATIO:
            sev = "Critical" if txn_ratio < config.BIZ_CRITICAL_LOW_RATIO else "High"
            alerts.append(_alert(ts, "VOLUME_LOW", sev, "Transaction volume significantly below expected level",
                f"Transaction volume is low for {label}. Expected about {exp_txn:.0f} transactions, "
                f"actual {act_txn:.0f} ({txn_ratio:.0%} of expected).", key))
        elif txn_ratio > config.BIZ_HIGH_RATIO:
            alerts.append(_alert(ts, "VOLUME_HIGH", "Medium", "Transaction volume significantly above expected level",
                f"Transaction volume is high for {label}. Expected about {exp_txn:.0f} transactions, "
                f"actual {act_txn:.0f} ({txn_ratio:.0%} of expected).", key))

    # ---- category level ----
    if category_hourly is not None and not category_hourly.empty:
        pivot = (category_hourly.pivot_table(index="hour_start", columns="category",
                                             values="revenue", aggfunc="sum")
                 .reindex(full_index).fillna(0.0))
        for category in pivot.columns:
            series = pivot[category]
            for ts in recent:
                expected = _expected_same_hour(series, ts)
                if expected is None or expected < MIN_EXPECTED_CATEGORY_REVENUE:
                    continue
                actual = float(series.loc[ts])
                ratio = actual / expected
                key = f"{ts:%Y-%m-%d %H:%M:%S}|{category}"
                if ratio >= config.CATEGORY_SURGE_RATIO:
                    sev = "High" if ratio >= 3 else "Medium"
                    alerts.append(_alert(ts, "CATEGORY_SURGE", sev, f"{category} revenue surge",
                        f"{category} revenue is {ratio:.1f}x the expected level for {_hour_label(ts)} "
                        f"(expected {format_inr(expected)}, actual {format_inr(actual)}).", key))
                elif ratio <= config.CATEGORY_DROP_RATIO:
                    alerts.append(_alert(ts, "CATEGORY_DROP", "Medium", f"{category} revenue drop",
                        f"{category} revenue is only {ratio:.0%} of the expected level for {_hour_label(ts)} "
                        f"(expected {format_inr(expected)}, actual {format_inr(actual)}).", key))
    return alerts