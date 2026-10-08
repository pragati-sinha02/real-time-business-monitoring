"""Back-fill historical transactions so the model has something to learn from.

Run:  python -m src.seed_history          (skips if data already exists)
      python -m src.seed_history --reset  (deletes everything first)
"""
import argparse
from collections import Counter
from datetime import datetime

from . import config, database
from .data_generator import generate_history
from .logger import get_logger

log = get_logger("seed")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="delete all existing rows first")
    parser.add_argument("--days", type=int, default=config.HISTORY_DAYS)
    args = parser.parse_args()

    ok, message = database.check_connection()
    log.info(message)
    if not ok:
        raise SystemExit(1)

    existing = database.table_count("transactions")
    if existing > 0 and not args.reset:
        log.info("transactions table already has %s rows. Nothing to do "
                 "(use --reset to start fresh).", f"{existing:,}")
        return
    if args.reset:
        database.reset_tables()
        log.info("All existing rows deleted.")

    end_time = datetime.now().replace(microsecond=0)
    log.info("Generating %d days of history...", args.days)
    rows = generate_history(end_time, args.days, start_counter=0)
    database.insert_transactions(rows)

    counts = Counter(r["injected_anomaly_type"] for r in rows if r["injected_anomaly_type"])
    log.info("Inserted %s historical transactions.", f"{len(rows):,}")
    log.info("Injected anomalies (simulator ground truth): %s", dict(counts))
    log.info("Next step:  python -m src.train_model")


if __name__ == "__main__":
    main()