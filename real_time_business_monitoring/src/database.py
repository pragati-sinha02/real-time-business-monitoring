"""All MySQL access lives here (connection, reading, writing)."""
from decimal import Decimal
from functools import lru_cache
from typing import Optional

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

from . import config

ALLOWED_TABLES = {"transactions", "transaction_scores", "alerts"}

INSERT_TRANSACTION_SQL = """
INSERT INTO transactions
 (transaction_id, txn_timestamp, customer_id, product_id, category, quantity,
  unit_price, total_amount, payment_method, city, device_type, injected_anomaly_type)
VALUES
 (:transaction_id, :txn_timestamp, :customer_id, :product_id, :category, :quantity,
  :unit_price, :total_amount, :payment_method, :city, :device_type, :injected_anomaly_type)
"""

INSERT_SCORE_SQL = """
INSERT IGNORE INTO transaction_scores
 (transaction_id, z_score, z_flag, iso_score, iso_flag, is_anomaly,
  risk_score, risk_level, reasons)
VALUES
 (:transaction_id, :z_score, :z_flag, :iso_score, :iso_flag, :is_anomaly,
  :risk_score, :risk_level, :reasons)
"""

INSERT_ALERT_SQL = """
INSERT IGNORE INTO alerts
 (event_time, alert_type, severity, title, message, related_key, risk_score)
VALUES
 (:event_time, :alert_type, :severity, :title, :message, :related_key, :risk_score)
"""


@lru_cache(maxsize=1)
def get_engine():
    """Create (once) the connection engine. URL.create safely handles special characters in passwords."""
    url = URL.create(
        "mysql+pymysql",
        username=config.DB_USER,
        password=config.DB_PASSWORD,
        host=config.DB_HOST,
        port=config.DB_PORT,
        database=config.DB_NAME,
        query={"charset": "utf8mb4"},
    )
    return create_engine(url, pool_pre_ping=True, pool_recycle=1800)


def check_connection():
    """Returns (True, message) or (False, error message). Never raises."""
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return True, f"Connected to MySQL successfully ({config.DB_HOST}:{config.DB_PORT}/{config.DB_NAME})."
    except Exception as exc:  # noqa: BLE001 - we want to show any problem in plain text
        return False, f"{type(exc).__name__}: {str(exc).splitlines()[0]}"


def _fix_decimals(df: pd.DataFrame) -> pd.DataFrame:
    for col in df.columns:
        if df[col].dtype == object:
            non_null = df[col].dropna()
            if len(non_null) and isinstance(non_null.iloc[0], Decimal):
                df[col] = df[col].astype(float)
    return df


def read_df(query: str, params: Optional[dict] = None) -> pd.DataFrame:
    with get_engine().connect() as conn:
        df = pd.read_sql_query(text(query), conn, params=params or {})
    return _fix_decimals(df)


def scalar(query: str, params: Optional[dict] = None):
    with get_engine().connect() as conn:
        return conn.execute(text(query), params or {}).scalar()


def execute(query: str, params: Optional[dict] = None) -> int:
    with get_engine().begin() as conn:
        return conn.execute(text(query), params or {}).rowcount


def executemany(query: str, rows: list, chunk_size: int = 2000) -> None:
    if not rows:
        return
    with get_engine().begin() as conn:
        for i in range(0, len(rows), chunk_size):
            conn.execute(text(query), rows[i:i + chunk_size])


def table_count(table: str) -> int:
    if table not in ALLOWED_TABLES:
        raise ValueError(f"Unknown table: {table}")
    return int(scalar(f"SELECT COUNT(*) FROM {table}") or 0)


def reset_tables() -> None:
    """Delete all rows (children first because of the foreign key)."""
    with get_engine().begin() as conn:
        conn.execute(text("DELETE FROM transaction_scores"))
        conn.execute(text("DELETE FROM alerts"))
        conn.execute(text("DELETE FROM transactions"))


def insert_transactions(rows: list) -> None:
    executemany(INSERT_TRANSACTION_SQL, rows)


def get_latest_timestamp():
    return scalar("SELECT MAX(txn_timestamp) FROM transactions")


def get_last_txn_number() -> int:
    value = scalar(
        "SELECT COALESCE(MAX(CAST(SUBSTRING(transaction_id, 4) AS UNSIGNED)), 0) FROM transactions"
    )
    return int(value or 0)


def load_transactions_since(start) -> pd.DataFrame:
    return read_df(
        """
        SELECT transaction_id, txn_timestamp, customer_id, product_id, category, quantity,
               unit_price, total_amount, payment_method, city, device_type
        FROM transactions
        WHERE txn_timestamp >= :start
        ORDER BY txn_timestamp, transaction_id
        """,
        {"start": start},
    )


def load_all_transactions() -> pd.DataFrame:
    return read_df(
        """
        SELECT transaction_id, txn_timestamp, customer_id, product_id, category, quantity,
               unit_price, total_amount, payment_method, city, device_type
        FROM transactions
        ORDER BY txn_timestamp, transaction_id
        """
    )


def get_unscored_ids(start) -> list:
    df = read_df(
        """
        SELECT t.transaction_id
        FROM transactions t
        LEFT JOIN transaction_scores s ON s.transaction_id = t.transaction_id
        WHERE t.txn_timestamp >= :start AND s.transaction_id IS NULL
        """,
        {"start": start},
    )
    return df["transaction_id"].tolist()


def save_scores(scored: pd.DataFrame) -> None:
    cols = ["transaction_id", "z_score", "z_flag", "iso_score", "iso_flag",
            "is_anomaly", "risk_score", "risk_level", "reasons"]
    executemany(INSERT_SCORE_SQL, scored[cols].to_dict("records"))


def insert_alert(alert: dict) -> bool:
    """Returns True if a NEW alert was stored (False if it already existed)."""
    with get_engine().begin() as conn:
        result = conn.execute(text(INSERT_ALERT_SQL), alert)
        return result.rowcount == 1