"""SQL used by the API (and by the pipeline for hourly aggregates)."""
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

import pandas as pd

from . import database

FROM_JOIN = ("FROM transactions t "
             "LEFT JOIN transaction_scores s ON s.transaction_id = t.transaction_id")


@dataclass
class Filters:
    start: Optional[datetime] = None
    end: Optional[datetime] = None
    categories: Optional[List[str]] = None
    cities: Optional[List[str]] = None
    payment_methods: Optional[List[str]] = None
    anomaly_status: str = "all"            # all | anomaly | normal
    risk_levels: Optional[List[str]] = None


def _in_clause(column, values, prefix, clauses, params):
    if not values:
        return
    names = []
    for i, value in enumerate(values):
        name = f"{prefix}_{i}"
        params[name] = value
        names.append(f":{name}")
    clauses.append(f"{column} IN ({', '.join(names)})")


def build_where(f: Filters):
    clauses, params = [], {}
    if f.start:
        clauses.append("t.txn_timestamp >= :start")
        params["start"] = f.start
    if f.end:
        clauses.append("t.txn_timestamp <= :end")
        params["end"] = f.end
    _in_clause("t.category", f.categories, "cat", clauses, params)
    _in_clause("t.city", f.cities, "city", clauses, params)
    _in_clause("t.payment_method", f.payment_methods, "pay", clauses, params)
    _in_clause("s.risk_level", f.risk_levels, "risk", clauses, params)
    if f.anomaly_status == "anomaly":
        clauses.append("s.is_anomaly = 1")
    elif f.anomaly_status == "normal":
        clauses.append("COALESCE(s.is_anomaly, 0) = 0")
    where = (" AND " + " AND ".join(clauses)) if clauses else ""
    return where, params


def kpis(f: Filters) -> dict:
    where, params = build_where(f)
    sql = f"""
        SELECT COUNT(*) AS transaction_count,
               COALESCE(SUM(t.total_amount), 0) AS total_revenue,
               COALESCE(AVG(t.total_amount), 0) AS avg_transaction_value,
               COALESCE(SUM(s.is_anomaly = 1), 0) AS anomaly_count,
               COALESCE(SUM(s.risk_level IN ('High','Critical')), 0) AS high_risk_count,
               COALESCE(SUM(s.risk_level = 'Critical'), 0) AS critical_count,
               COALESCE(SUM(CASE WHEN s.risk_level IN ('High','Critical')
                                 THEN t.total_amount ELSE 0 END), 0) AS revenue_at_risk
        {FROM_JOIN}
        WHERE 1=1{where}
    """
    row = database.read_df(sql, params).iloc[0]
    count = int(row["transaction_count"])
    anomalies = int(row["anomaly_count"])
    return {
        "transaction_count": count,
        "total_revenue": float(row["total_revenue"]),
        "avg_transaction_value": float(row["avg_transaction_value"]),
        "anomaly_count": anomalies,
        "anomaly_rate_pct": round(100 * anomalies / count, 2) if count else 0.0,
        "high_risk_count": int(row["high_risk_count"]),
        "critical_count": int(row["critical_count"]),
        "revenue_at_risk": float(row["revenue_at_risk"]),
    }


def _bucket(seconds: int) -> str:
    return ("TIMESTAMP(DATE(t.txn_timestamp), "
            f"SEC_TO_TIME(FLOOR(TIME_TO_SEC(t.txn_timestamp) / {seconds}) * {seconds}))")


GROUP_EXPRESSIONS = {
    "category": "t.category",
    "city": "t.city",
    "payment_method": "t.payment_method",
    "device_type": "t.device_type",
    "risk_level": "COALESCE(s.risk_level, 'Unscored')",
    "anomaly_status": "CASE WHEN s.is_anomaly = 1 THEN 'Anomaly' ELSE 'Normal' END",
    "hour_of_day": "HOUR(t.txn_timestamp)",
    "day": "DATE(t.txn_timestamp)",
    "hour": _bucket(3600),
    "15min": _bucket(900),
}
TIME_LIKE = {"hour_of_day", "day", "hour", "15min"}


def grouped(group_by: str, f: Filters) -> pd.DataFrame:
    expression = GROUP_EXPRESSIONS[group_by]      # API validates group_by before calling
    where, params = build_where(f)
    order = "label ASC" if group_by in TIME_LIKE else "revenue DESC"
    sql = f"""
        SELECT {expression} AS label,
               COALESCE(SUM(t.total_amount), 0) AS revenue,
               COUNT(*) AS transactions,
               COALESCE(SUM(COALESCE(s.is_anomaly, 0)), 0) AS anomalies
        {FROM_JOIN}
        WHERE 1=1{where}
        GROUP BY label
        ORDER BY {order}
    """
    df = database.read_df(sql, params)
    if not df.empty:
        df["label"] = df["label"].astype(str)
        df["transactions"] = df["transactions"].astype(int)
        df["anomalies"] = df["anomalies"].astype(int)
    return df


def transactions(f: Filters, limit: int = 100, only_anomalies: bool = False) -> pd.DataFrame:
    where, params = build_where(f)
    if only_anomalies:
        where += " AND s.is_anomaly = 1"
    params["limit"] = int(limit)
    sql = f"""
        SELECT t.transaction_id, t.txn_timestamp, t.customer_id, t.product_id, t.category,
               t.quantity, t.unit_price, t.total_amount, t.payment_method, t.city, t.device_type,
               s.is_anomaly, s.risk_score, s.risk_level, s.reasons
        {FROM_JOIN}
        WHERE 1=1{where}
        ORDER BY t.txn_timestamp DESC, t.transaction_id DESC
        LIMIT :limit
    """
    return database.read_df(sql, params)


def top_customers(f: Filters, limit: int = 10) -> pd.DataFrame:
    where, params = build_where(f)
    params["limit"] = int(limit)
    sql = f"""
        SELECT t.customer_id,
               COUNT(*) AS transactions,
               SUM(t.total_amount) AS revenue,
               AVG(t.total_amount) AS avg_transaction_value,
               COALESCE(SUM(COALESCE(s.is_anomaly, 0)), 0) AS anomalies
        {FROM_JOIN}
        WHERE 1=1{where}
        GROUP BY t.customer_id
        ORDER BY revenue DESC
        LIMIT :limit
    """
    return database.read_df(sql, params)


def alerts(limit: int = 50, severity: Optional[str] = None) -> pd.DataFrame:
    params = {"limit": int(limit)}
    where = ""
    if severity:
        where = "WHERE severity = :severity"
        params["severity"] = severity
    sql = f"""
        SELECT alert_id, event_time, alert_type, severity, title, message, related_key, risk_score
        FROM alerts {where}
        ORDER BY event_time DESC, alert_id DESC
        LIMIT :limit
    """
    return database.read_df(sql, params)


def filter_options() -> dict:
    def distinct(column):
        df = database.read_df(f"SELECT DISTINCT {column} AS v FROM transactions ORDER BY v")
        return df["v"].tolist()
    return {"categories": distinct("category"), "cities": distinct("city"),
            "payment_methods": distinct("payment_method")}


def hourly_series(start) -> pd.DataFrame:
    sql = """
        SELECT TIMESTAMP(DATE(txn_timestamp), SEC_TO_TIME(HOUR(txn_timestamp) * 3600)) AS hour_start,
               SUM(total_amount) AS revenue, COUNT(*) AS transactions
        FROM transactions
        WHERE txn_timestamp >= :start
        GROUP BY hour_start
        ORDER BY hour_start
    """
    df = database.read_df(sql, {"start": pd.Timestamp(start).to_pydatetime()})
    if df.empty:
        return pd.DataFrame(columns=["revenue", "transactions"],
                            index=pd.DatetimeIndex([], name="hour_start"), dtype=float)
    df["hour_start"] = pd.to_datetime(df["hour_start"])
    df["revenue"] = df["revenue"].astype(float)
    df["transactions"] = df["transactions"].astype(int)
    return df.set_index("hour_start")


def category_hourly_series(start) -> pd.DataFrame:
    sql = """
        SELECT TIMESTAMP(DATE(txn_timestamp), SEC_TO_TIME(HOUR(txn_timestamp) * 3600)) AS hour_start,
               category, SUM(total_amount) AS revenue
        FROM transactions
        WHERE txn_timestamp >= :start
        GROUP BY hour_start, category
        ORDER BY hour_start
    """
    df = database.read_df(sql, {"start": pd.Timestamp(start).to_pydatetime()})
    if not df.empty:
        df["hour_start"] = pd.to_datetime(df["hour_start"])
        df["revenue"] = df["revenue"].astype(float)
    return df