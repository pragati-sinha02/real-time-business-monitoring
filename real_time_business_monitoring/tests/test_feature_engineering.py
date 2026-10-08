import pandas as pd

from src.feature_engineering import FEATURE_COLUMNS, build_features, get_model_matrix


def make_df():
    base = pd.Timestamp("2026-01-01 10:00:00")
    rows = []
    for i in range(6):   # customer C1: one order every 2 minutes
        rows.append(dict(transaction_id=f"TXN{i:08d}", txn_timestamp=base + pd.Timedelta(minutes=2 * i),
                         customer_id="C1", product_id="GRO-01", category="Grocery", quantity=1,
                         unit_price=500.0, total_amount=500.0, payment_method="UPI",
                         city="Patna", device_type="Mobile"))
    rows.append(dict(transaction_id="TXN00000006", txn_timestamp=base + pd.Timedelta(minutes=5),
                     customer_id="C2", product_id="GRO-02", category="Grocery", quantity=2,
                     unit_price=900.0, total_amount=1800.0, payment_method="Wallet",
                     city="Delhi", device_type="Desktop"))
    return pd.DataFrame(rows)


def test_rolling_counts_and_columns():
    feats = build_features(make_df())
    last = feats[feats["transaction_id"] == "TXN00000005"].iloc[0]
    assert last["txns_last_10min"] == 6
    assert last["txns_last_1h"] == 6
    first = feats[feats["transaction_id"] == "TXN00000000"].iloc[0]
    assert first["txns_last_10min"] == 1
    assert first["customer_txn_count"] == 0
    for col in FEATURE_COLUMNS:
        assert col in feats.columns


def test_model_matrix_has_no_missing_values():
    matrix = get_model_matrix(build_features(make_df()))
    assert list(matrix.columns) == FEATURE_COLUMNS
    assert not matrix.isna().any().any()