"""Turn cleaned transactions into numeric features for anomaly detection."""
import numpy as np
import pandas as pd

# These columns are fed to the Isolation Forest (order matters and is saved with the model).
FEATURE_COLUMNS = [
    "log_amount", "amount_ratio", "txns_last_10min", "txns_last_1h",
    "log_velocity_1h", "amount_zscore", "category_affinity", "hour_of_day", "is_night",
]

MIN_CUSTOMER_HISTORY = 3     # need this many past orders to trust the customer average
MIN_AFFINITY_HISTORY = 5     # need this many past orders to trust category affinity
DEFAULT_AFFINITY = 0.2


def _rolling_window(df: pd.DataFrame, minutes: int):
    """For each row: how many transactions (and how much money) did the SAME customer
    make in the last `minutes` minutes, including the current one?
    `df` must be sorted by time with a default 0..n-1 index."""
    times_all = df["txn_timestamp"].to_numpy(dtype="datetime64[ns]")
    amounts_all = df["amount"].to_numpy(dtype=float)
    counts = np.zeros(len(df), dtype=int)
    sums = np.zeros(len(df), dtype=float)
    window = np.timedelta64(minutes, "m")

    for _, idx in df.groupby("customer_id").indices.items():
        t = times_all[idx]
        a = amounts_all[idx]
        left = np.searchsorted(t, t - window, side="left")   # first row inside the window
        pos = np.arange(len(idx))
        counts[idx] = pos - left + 1
        cumulative = np.concatenate(([0.0], np.cumsum(a)))
        sums[idx] = cumulative[pos + 1] - cumulative[left]
    return counts, sums


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df.copy()

    df = df.copy()
    df["txn_timestamp"] = pd.to_datetime(df["txn_timestamp"])
    df = df.sort_values(["txn_timestamp", "transaction_id"]).reset_index(drop=True)

    # --- amount and time ---
    df["amount"] = df["total_amount"].astype(float)
    df["log_amount"] = np.log1p(df["amount"])
    df["hour_of_day"] = df["txn_timestamp"].dt.hour
    df["day_of_week"] = df["txn_timestamp"].dt.dayofweek
    df["is_night"] = (df["hour_of_day"] < 6).astype(int)

    # --- category level ---
    by_cat = df.groupby("category")
    df["category_avg_amount"] = by_cat["amount"].transform("mean")
    cat_mean = by_cat["log_amount"].transform("mean")
    cat_std = by_cat["log_amount"].transform("std").fillna(1.0).replace(0.0, 1.0)
    df["amount_zscore"] = (df["log_amount"] - cat_mean) / cat_std

    # --- customer history (only PREVIOUS transactions) ---
    by_cust = df.groupby("customer_id")
    prev_count = by_cust.cumcount()
    prev_sum = by_cust["amount"].cumsum() - df["amount"]
    cust_avg = prev_sum / prev_count.where(prev_count > 0)
    df["customer_txn_count"] = prev_count
    df["customer_avg_amount"] = cust_avg.where(prev_count >= MIN_CUSTOMER_HISTORY,
                                               df["category_avg_amount"])
    df["amount_deviation"] = df["amount"] - df["customer_avg_amount"]
    df["amount_ratio"] = (df["amount"] / df["customer_avg_amount"]).clip(upper=50)

    prev_cat_count = df.groupby(["customer_id", "category"]).cumcount()
    affinity = prev_cat_count / prev_count.where(prev_count > 0)
    df["category_affinity"] = affinity.where(prev_count >= MIN_AFFINITY_HISTORY, DEFAULT_AFFINITY)

    # --- short-term behaviour ---
    count_10, _ = _rolling_window(df, 10)
    count_60, sum_60 = _rolling_window(df, 60)
    df["txns_last_10min"] = count_10
    df["txns_last_1h"] = count_60
    df["spending_velocity_1h"] = sum_60
    df["log_velocity_1h"] = np.log1p(sum_60)
    df["velocity_ratio"] = sum_60 / df["customer_avg_amount"]

    return df


def get_model_matrix(df: pd.DataFrame) -> pd.DataFrame:
    """The clean numeric table given to the model (no NaN / infinity)."""
    X = df[FEATURE_COLUMNS].astype(float)
    return X.replace([np.inf, -np.inf], np.nan).fillna(0.0)