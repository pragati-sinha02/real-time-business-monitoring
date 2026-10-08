from datetime import datetime

from src.data_generator import TransactionGenerator

START = datetime(2026, 1, 1, 12, 0, 0)


def test_normal_transactions_are_valid_and_unlabelled():
    gen = TransactionGenerator(START, anomaly_rate=0.0, scenario_rate=0.0, seed=1)
    rows = [gen.next_transaction() for _ in range(300)]
    assert len({r["transaction_id"] for r in rows}) == 300
    for r in rows:
        assert r["injected_anomaly_type"] is None
        assert r["total_amount"] > 0 and r["unit_price"] > 0 and r["quantity"] > 0
        assert abs(r["total_amount"] - r["quantity"] * r["unit_price"]) < 0.011
    stamps = [r["txn_timestamp"] for r in rows]
    assert stamps == sorted(stamps)


def test_anomaly_rate_one_labels_every_row():
    gen = TransactionGenerator(START, anomaly_rate=1.0, scenario_rate=0.0, seed=2)
    rows = [gen.next_transaction() for _ in range(100)]
    assert all(r["injected_anomaly_type"] is not None for r in rows)