"""Risk score (0-100), risk level and human-readable reasons."""
import pandas as pd

from .utils import format_inr

REASON_SEPARATOR = " | "
W_ISO, W_Z, W_BEHAVIOR = 0.55, 0.25, 0.20
LEVEL_BANDS = [(30, "Low"), (60, "Medium"), (80, "High"), (100, "Critical")]
FALLBACK_REASON = "Overall pattern is statistically unusual, but no single simple rule explains it"

# (rule name, mask function over the DataFrame, text function for one row)
RULES = [
    ("customer_average",
     lambda d: (d["amount_ratio"] >= 5) & (d["customer_txn_count"] >= 3),
     lambda r: f"Amount is {r['amount_ratio']:.1f}x higher than this customer's average"),
    ("category_level",
     lambda d: d["amount_zscore"] >= 3,
     lambda r: f"Amount is unusually high for the {r['category']} category (z-score {r['amount_zscore']:.1f})"),
    ("frequency",
     lambda d: d["txns_last_10min"] >= 4,
     lambda r: f"Unusually high transaction frequency ({int(r['txns_last_10min'])} transactions in 10 minutes)"),
    ("velocity",
     lambda d: (d["txns_last_1h"] >= 3) & (d["velocity_ratio"] >= 5),
     lambda r: f"Unusual spending velocity ({format_inr(r['spending_velocity_1h'])} spent in the last hour)"),
    ("category_behavior",
     lambda d: (d["category_affinity"] <= 0.03) & (d["customer_txn_count"] >= 20),
     lambda r: f"Unusual category behavior (this customer rarely buys {r['category']})"),
    ("night_time",
     lambda d: (d["is_night"] == 1) & (d["amount_ratio"] >= 2.5),
     lambda r: f"Large purchase during night hours ({int(r['hour_of_day']):02d}:00)"),
]


def risk_level(score: int) -> str:
    for upper, name in LEVEL_BANDS:
        if score <= upper:
            return name
    return "Critical"


def add_risk_scores(scored: pd.DataFrame, bundle: dict) -> pd.DataFrame:
    df = scored.copy()
    if df.empty:
        df["risk_score"] = pd.Series(dtype=int)
        df["risk_level"] = pd.Series(dtype=object)
        df["reasons"] = pd.Series(dtype=object)
        return df

    typical = float(bundle["score_typical"])
    extreme = float(bundle["score_extreme"])
    span = max(typical - extreme, 1e-6)

    iso_norm = ((typical - df["iso_score"]) / span).clip(0, 1)
    z_norm = ((df["amount_zscore"].abs() - 1.0) / 3.0).clip(0, 1)
    masks = pd.DataFrame({name: fn(df) for name, fn, _ in RULES}, index=df.index)
    behavior_norm = (masks.sum(axis=1) / 3.0).clip(0, 1)

    raw = 100 * (W_ISO * iso_norm + W_Z * z_norm + W_BEHAVIOR * behavior_norm)
    df["risk_score"] = raw.round().clip(0, 100).astype(int)
    df["risk_level"] = df["risk_score"].map(risk_level)

    reasons = pd.Series("", index=df.index, dtype=object)
    needs_text = (df["risk_score"] >= 31) | (df["is_anomaly"] == 1)
    for idx in df.index[needs_text]:
        row = df.loc[idx]
        parts = [text_fn(row) for name, _, text_fn in RULES if masks.at[idx, name]]
        reasons.at[idx] = REASON_SEPARATOR.join(parts) if parts else FALLBACK_REASON
    df["reasons"] = reasons
    return df