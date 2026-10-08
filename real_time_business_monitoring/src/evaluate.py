"""Measure detector quality against the simulator's ground truth.

Run:  python -m src.evaluate            (all scored rows)
      python -m src.evaluate --hours 24 (only the most recent 24 simulated hours)
"""
import argparse

import pandas as pd
from sklearn.metrics import precision_recall_fscore_support

from . import database


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hours", type=int, default=None)
    args = parser.parse_args()

    df = database.read_df("""
        SELECT t.transaction_id, t.txn_timestamp, t.injected_anomaly_type,
               s.z_flag, s.iso_flag, s.is_anomaly
        FROM transactions t JOIN transaction_scores s ON s.transaction_id = t.transaction_id
    """)
    if df.empty:
        print("No scored transactions yet. Run:  python -m src.pipeline --once")
        return
    if args.hours:
        df["txn_timestamp"] = pd.to_datetime(df["txn_timestamp"])
        df = df[df["txn_timestamp"] >= df["txn_timestamp"].max() - pd.Timedelta(hours=args.hours)]

    y_true = df["injected_anomaly_type"].notna().astype(int)
    print(f"\nRows evaluated: {len(df):,} | injected anomalies: {int(y_true.sum()):,} "
          f"({100 * y_true.mean():.2f}%)\n")
    print(f"{'Detector':<28}{'Precision':>10}{'Recall':>10}{'F1':>8}{'Flagged':>10}")
    for name, col in [("Z-score baseline", "z_flag"), ("Isolation Forest", "iso_flag"),
                      ("Combined (is_anomaly)", "is_anomaly")]:
        p, r, f, _ = precision_recall_fscore_support(y_true, df[col], average="binary", zero_division=0)
        print(f"{name:<28}{p:>10.2f}{r:>10.2f}{f:>8.2f}{int(df[col].sum()):>10,}")

    print("\nRecall of the combined detector by injected anomaly type:")
    typed = df[df["injected_anomaly_type"].notna()]
    print(typed.groupby("injected_anomaly_type")["is_anomaly"].agg(["mean", "count"])
          .rename(columns={"mean": "recall", "count": "rows"}).round(2))
    print("\nNote: this model was trained on the same history it is judged on (in-sample), "
          "and the first row of a burst looks normal because features only see the past. "
          "Use --hours to look at newer data.")


if __name__ == "__main__":
    main()