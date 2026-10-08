"""Train the Isolation Forest on stored history.   Run:  python -m src.train_model"""
from . import anomaly_detection, config, database, feature_engineering, preprocessing
from .logger import get_logger

log = get_logger("train")


def main():
    ok, message = database.check_connection()
    log.info(message)
    if not ok:
        raise SystemExit(1)

    raw = database.load_all_transactions()
    if len(raw) < 1000:
        log.error("Only %d rows found. Run  python -m src.seed_history  first.", len(raw))
        raise SystemExit(1)

    clean = preprocessing.clean_transactions(raw)
    features = feature_engineering.build_features(clean)
    bundle = anomaly_detection.train_isolation_forest(features)
    anomaly_detection.save_bundle(bundle)

    scored = anomaly_detection.score_transactions(features, bundle)
    log.info("Model trained on %s transactions using %d features.",
             f"{bundle['n_rows']:,}", len(bundle["features"]))
    log.info("Share flagged by Isolation Forest in training data: %.2f%%", 100 * scored["iso_flag"].mean())
    log.info("Share flagged by Z-score baseline: %.2f%%", 100 * scored["z_flag"].mean())
    log.info("Model saved to %s", config.MODEL_PATH)
    log.info("Next step:  python -m src.pipeline --once")


if __name__ == "__main__":
    main()