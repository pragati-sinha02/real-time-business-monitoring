"""The monitoring worker: score new transactions, raise alerts, check business KPIs.

Run forever:  python -m src.pipeline
Run once:     python -m src.pipeline --once     (scores the whole history, then exits)
"""
import argparse
import time

import pandas as pd

from . import (alerts, anomaly_detection, business_anomalies, config, database,
               feature_engineering, preprocessing, queries, risk_scoring)
from .logger import get_logger

log = get_logger("pipeline")


def run_once(bundle: dict) -> dict:
    started = time.time()
    latest = database.get_latest_timestamp()
    if latest is None:
        return {"scored": 0, "anomalies": 0, "alerts": 0, "seconds": 0.0}

    data_now = pd.Timestamp(latest)
    start = (data_now - pd.Timedelta(hours=config.LOOKBACK_HOURS)).to_pydatetime()
    scored_count = anomaly_count = alert_count = 0

    unscored_ids = database.get_unscored_ids(start)
    if unscored_ids:
        raw = database.load_transactions_since(start)
        clean = preprocessing.clean_transactions(raw)
        features = feature_engineering.build_features(clean)
        new_rows = features[features["transaction_id"].isin(set(unscored_ids))].copy()
        if not new_rows.empty:
            scored = anomaly_detection.score_transactions(new_rows, bundle, config.Z_THRESHOLD)
            scored = risk_scoring.add_risk_scores(scored, bundle)
            database.save_scores(scored)
            scored_count = len(scored)
            anomaly_count = int(scored["is_anomaly"].sum())
            alert_count += alerts.create_transaction_alerts(scored, data_now)

    try:
        hourly = queries.hourly_series(start)
        category_hourly = queries.category_hourly_series(start)
        business_alerts = business_anomalies.detect_business_anomalies(hourly, category_hourly, data_now)
        alert_count += alerts.create_business_alerts(business_alerts)
    except Exception as exc:  # noqa: BLE001 - business checks must never stop scoring
        log.error("Business KPI check failed: %s", exc)

    return {"scored": scored_count, "anomalies": anomaly_count, "alerts": alert_count,
            "seconds": round(time.time() - started, 2)}


def main():
    parser = argparse.ArgumentParser(description="Monitoring pipeline worker")
    parser.add_argument("--once", action="store_true", help="run a single cycle and exit")
    parser.add_argument("--interval", type=float, default=config.PIPELINE_INTERVAL_SECONDS)
    args = parser.parse_args()

    ok, message = database.check_connection()
    log.info(message)
    if not ok:
        raise SystemExit(1)
    try:
        bundle = anomaly_detection.load_bundle()
    except FileNotFoundError as exc:
        log.error(str(exc))
        raise SystemExit(1)

    if args.once:
        result = run_once(bundle)
        log.info("Scored %s transactions | anomalies: %s | new alerts: %s | %.1fs",
                 f"{result['scored']:,}", f"{result['anomalies']:,}", result["alerts"], result["seconds"])
        return

    log.info("Pipeline running every %.0f seconds. Press Ctrl+C to stop.", args.interval)
    try:
        while True:
            try:
                result = run_once(bundle)
                if result["scored"] or result["alerts"]:
                    log.info("Scored %d new | anomalies: %d | new alerts: %d | %.1fs",
                             result["scored"], result["anomalies"], result["alerts"], result["seconds"])
            except Exception as exc:  # noqa: BLE001
                log.error("Pipeline cycle failed: %s", exc)
            time.sleep(args.interval)
    except KeyboardInterrupt:
        log.info("Pipeline stopped.")


if __name__ == "__main__":
    main()