import numpy as np
import pandas as pd

from src.anomaly_detection import score_transactions, train_isolation_forest
from src.feature_engineering import FEATURE_COLUMNS


def make_features():
    rng = np.random.default_rng(0)
    n = 500
    normal = pd.DataFrame({
        "log_amount": rng.normal(8, 0.5, n),
        "amount_ratio": rng.normal(1, 0.2, n).clip(0.3, 3),
        "txns_last_10min": np.ones(n),
        "txns_last_1h": np.ones(n),
        "log_velocity_1h": rng.normal(8, 0.5, n),
        "amount_zscore": rng.normal(0, 1, n),
        "category_affinity": np.full(n, 0.4),
        "hour_of_day": rng.integers(8, 22, n),
        "is_night": np.zeros(n),
    })
    extreme = pd.DataFrame([{"log_amount": 12.0, "amount_ratio": 30.0, "txns_last_10min": 8,
                             "txns_last_1h": 9, "log_velocity_1h": 13.0, "amount_zscore": 8.0,
                             "category_affinity": 0.0, "hour_of_day": 3, "is_night": 1}])
    return pd.concat([normal, extreme], ignore_index=True)[FEATURE_COLUMNS]


def test_extreme_row_is_flagged():
    feats = make_features()
    bundle = train_isolation_forest(feats, contamination=0.02)
    scored = score_transactions(feats, bundle, z_threshold=3.0)
    last = scored.iloc[-1]
    assert last["iso_flag"] == 1
    assert last["z_flag"] == 1
    assert last["is_anomaly"] == 1
    assert bundle["score_typical"] > bundle["score_extreme"]
    assert scored["iso_flag"].mean() < 0.10