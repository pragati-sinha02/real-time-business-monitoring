"""Cleaning step: make sure the data is valid before computing features."""
import pandas as pd

REQUIRED_COLUMNS = [
    "transaction_id", "txn_timestamp", "customer_id", "product_id", "category",
    "quantity", "unit_price", "total_amount", "payment_method", "city", "device_type",
]
TEXT_COLUMNS = ["transaction_id", "customer_id", "product_id", "category",
                "payment_method", "city", "device_type"]


def clean_transactions(df: pd.DataFrame) -> pd.DataFrame:
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Missing columns: {missing}")

    df = df[REQUIRED_COLUMNS].copy()
    df["txn_timestamp"] = pd.to_datetime(df["txn_timestamp"], errors="coerce")
    for col in ["quantity", "unit_price", "total_amount"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=REQUIRED_COLUMNS)
    df = df[(df["quantity"] > 0) & (df["unit_price"] > 0) & (df["total_amount"] > 0)]
    for col in TEXT_COLUMNS:
        df[col] = df[col].astype(str).str.strip()
    df["quantity"] = df["quantity"].astype(int)
    df = df.drop_duplicates(subset="transaction_id")
    return df.sort_values(["txn_timestamp", "transaction_id"]).reset_index(drop=True)