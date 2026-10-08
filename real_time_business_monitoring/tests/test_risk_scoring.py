import pandas as pd

from src.risk_scoring import add_risk_scores, risk_level

BUNDLE = {"score_typical": -0.45, "score_extreme": -0.75}


def test_risk_level_boundaries():
    assert risk_level(0) == "Low" and risk_level(30) == "Low"
    assert risk_level(31) == "Medium" and risk_level(60) == "Medium"
    assert risk_level(61) == "High" and risk_level(80) == "High"
    assert risk_level(81) == "Critical" and risk_level(100) == "Critical"


def base_row(**overrides):
    row = dict(iso_score=-0.40, amount_zscore=0.2, amount_ratio=1.0, customer_txn_count=30,
               txns_last_10min=1, txns_last_1h=1, velocity_ratio=1.0, spending_velocity_1h=1000.0,
               category_affinity=0.4, is_night=0, hour_of_day=14, category="Grocery",
               amount=1000.0, is_anomaly=0)
    row.update(overrides)
    return row


def test_normal_and_extreme_rows():
    df = pd.DataFrame([base_row(),
                       base_row(iso_score=-0.75, amount_zscore=5.0, amount_ratio=12.0,
                                amount=90000.0, is_anomaly=1)])
    out = add_risk_scores(df, BUNDLE)
    assert out.loc[0, "risk_level"] == "Low" and out.loc[0, "reasons"] == ""
    assert out.loc[1, "risk_score"] >= 81 and out.loc[1, "risk_level"] == "Critical"
    assert "higher than this customer's average" in out.loc[1, "reasons"]