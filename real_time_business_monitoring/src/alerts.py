"""Create alerts in MySQL and write them to logs/alerts.log."""
from datetime import timedelta

import pandas as pd

from . import config, database
from .logger import get_logger
from .risk_scoring import REASON_SEPARATOR
from .utils import format_inr

alert_log = get_logger("alerts", "alerts.log")


def build_transaction_message(row) -> str:
    title = "CRITICAL ANOMALY DETECTED" if row.risk_level == "Critical" else "HIGH-RISK TRANSACTION DETECTED"
    reasons = [r for r in str(row.reasons).split(REASON_SEPARATOR) if r]
    reason_lines = "\n".join(f"- {r}" for r in reasons) or "- (no reason available)"
    return (
        f"{title}\n\n"
        f"Transaction: {row.transaction_id}\n"
        f"Amount: {format_inr(row.amount)}\n"
        f"Customer: {row.customer_id}\n"
        f"Risk Score: {int(row.risk_score)}\n\n"
        f"Reasons:\n{reason_lines}\n\n"
        f"Note: reasons are indicators from simple rules, not confirmed causes."
    )


def create_transaction_alerts(scored: pd.DataFrame, data_now) -> int:
    """Alert for high-risk transactions in the last few (simulated) hours."""
    if scored.empty:
        return 0
    window_start = pd.Timestamp(data_now) - timedelta(hours=config.ALERT_WINDOW_HOURS)
    selected = scored[(scored["risk_score"] >= config.ALERT_RISK_THRESHOLD)
                      & (scored["txn_timestamp"] >= window_start)]
    created = 0
    for row in selected.itertuples():
        severity = "Critical" if row.risk_level == "Critical" else "High"
        message = build_transaction_message(row)
        alert = {
            "event_time": row.txn_timestamp.to_pydatetime(),
            "alert_type": "TRANSACTION_ANOMALY",
            "severity": severity,
            "title": message.splitlines()[0],
            "message": message,
            "related_key": row.transaction_id,
            "risk_score": int(row.risk_score),
        }
        if database.insert_alert(alert):
            created += 1
            alert_log.warning("\n%s", message)
    return created


def create_business_alerts(alerts: list) -> int:
    created = 0
    for alert in alerts:
        if database.insert_alert(alert):
            created += 1
            alert_log.warning("%s | %s | %s", alert["severity"].upper(), alert["title"], alert["message"])
    return created