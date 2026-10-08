"""Realistic transaction generator (simulated clock) + live insert loop.

Run live:   python -m src.data_generator
Options:    --anomaly-rate 0.05   --interval 0.5   --scenario volume_drop
"""
import argparse
import random
import time
from collections import deque
from datetime import datetime, timedelta

from . import config, database
from .logger import get_logger
from .utils import format_inr

log = get_logger("generator")

CATEGORY_PRODUCTS = {
    "Electronics": [("ELE-01", 2500), ("ELE-02", 4500), ("ELE-03", 3500),
                    ("ELE-04", 1800), ("ELE-05", 3000), ("ELE-06", 9000)],
    "Fashion": [("FAS-01", 900), ("FAS-02", 2200), ("FAS-03", 3200),
                ("FAS-04", 3800), ("FAS-05", 1600), ("FAS-06", 2600)],
    "Grocery": [("GRO-01", 650), ("GRO-02", 900), ("GRO-03", 1200),
                ("GRO-04", 450), ("GRO-05", 700), ("GRO-06", 800)],
    "Home & Kitchen": [("HOM-01", 3200), ("HOM-02", 2800), ("HOM-03", 1500),
                       ("HOM-04", 700), ("HOM-05", 2400), ("HOM-06", 1100)],
    "Beauty": [("BEA-01", 1800), ("BEA-02", 2200), ("BEA-03", 1500),
               ("BEA-04", 1100), ("BEA-05", 600), ("BEA-06", 450)],
    "Sports": [("SPO-01", 900), ("SPO-02", 2800), ("SPO-03", 1800),
               ("SPO-04", 3400), ("SPO-05", 2600), ("SPO-06", 1500)],
}
CATEGORIES = list(CATEGORY_PRODUCTS)
DEFAULT_QUANTITIES = [1, 1, 1, 1, 2, 2, 3]
QUANTITY_CHOICES = {"Grocery": [1, 1, 2, 2, 3, 4]}

PAYMENT_METHODS = ["UPI", "Credit Card", "Debit Card", "Net Banking", "Cash on Delivery", "Wallet"]
PAYMENT_WEIGHTS = [45, 20, 15, 8, 7, 5]
CITIES = ["Mumbai", "Delhi", "Bengaluru", "Hyderabad", "Chennai",
          "Kolkata", "Pune", "Patna", "Ahmedabad", "Jaipur"]
CITY_WEIGHTS = [16, 16, 14, 10, 9, 8, 8, 5, 8, 6]
DEVICES = ["Mobile", "Desktop", "Tablet"]
DEVICE_WEIGHTS = [65, 25, 10]

# Relative traffic for each hour of the day (index = hour 0..23).
HOUR_MULTIPLIER = [0.45, 0.38, 0.35, 0.35, 0.40, 0.55,
                   0.80, 1.00, 1.20, 1.30, 1.40, 1.50,
                   1.60, 1.50, 1.30, 1.20, 1.20, 1.30,
                   1.50, 1.70, 1.80, 1.70, 1.30, 0.80]
NIGHT_HOURS = range(0, 6)

ANOMALY_TYPES = ["large_amount", "burst", "spending_spike", "unusual_category", "night_activity"]
ANOMALY_WEIGHTS = [30, 20, 15, 20, 15]
SCENARIOS = ["volume_drop", "revenue_drop", "category_surge"]

PROFILE_SEED = 12345  # fixed so customers behave the same in history and in live mode


class TransactionGenerator:
    def __init__(self, start_time, start_counter=0, anomaly_rate=None, n_customers=None,
                 base_gap_seconds=None, scenario_rate=None, seed=None):
        self.clock = start_time
        self.counter = start_counter
        self.anomaly_rate = config.ANOMALY_RATE if anomaly_rate is None else anomaly_rate
        self.base_gap = config.SIM_BASE_GAP_SECONDS if base_gap_seconds is None else base_gap_seconds
        self.scenario_rate = config.SCENARIO_RATE if scenario_rate is None else scenario_rate
        n = config.N_CUSTOMERS if n_customers is None else n_customers
        self.rng = random.Random(config.RANDOM_SEED if seed is None else seed)
        self.pending = deque()   # follow-up transactions of a burst / spike
        self.scenario = None     # dict(name, ends_at, category)
        self.events = []         # human-readable messages for the live loop
        self.customers, self.activity = self._make_customers(n)

    # ---------- setup ----------
    @staticmethod
    def _make_customers(n):
        rng = random.Random(PROFILE_SEED)
        customers, activity = [], []
        for i in range(n):
            prefs = rng.sample(CATEGORIES, 2)
            weights = [0.55 if c == prefs[0] else 0.37 if c == prefs[1] else 0.02 for c in CATEGORIES]
            customers.append({
                "customer_id": f"C{1001 + i}",
                "preferred": prefs,
                "category_weights": weights,
                "spend_level": min(1.8, max(0.6, rng.lognormvariate(0, 0.25))),
                "city": rng.choices(CITIES, CITY_WEIGHTS)[0],
                "payment": rng.choices(PAYMENT_METHODS, PAYMENT_WEIGHTS)[0],
                "device": rng.choices(DEVICES, DEVICE_WEIGHTS)[0],
            })
            activity.append(rng.lognormvariate(0, 0.5))
        return customers, activity

    # ---------- scenarios ----------
    def start_scenario(self, name, minutes=120):
        category = self.rng.choice(CATEGORIES) if name == "category_surge" else None
        self.scenario = {"name": name, "ends_at": self.clock + timedelta(minutes=minutes),
                         "category": category}
        extra = f" ({category})" if category else ""
        self.events.append(f"SCENARIO STARTED: {name}{extra} for ~{minutes} simulated minutes")

    def _update_scenario(self):
        if self.scenario and self.clock >= self.scenario["ends_at"]:
            self.events.append(f"SCENARIO ENDED: {self.scenario['name']}")
            self.scenario = None
        if self.scenario is None and self.rng.random() < self.scenario_rate:
            self.start_scenario(self.rng.choice(SCENARIOS), self.rng.randint(100, 180))

    def _scenario_name(self):
        return self.scenario["name"] if self.scenario else None

    # ---------- picking helpers ----------
    def _next_gap(self):
        mean = self.base_gap / HOUR_MULTIPLIER[self.clock.hour]
        if self._scenario_name() == "volume_drop":
            mean *= 4
        return min(self.rng.expovariate(1.0 / mean), mean * 6)

    def _pick_customer(self):
        weights = self.activity
        if self._scenario_name() == "category_surge":
            cat = self.scenario["category"]
            weights = [a * (6 if cat in c["preferred"] else 1)
                       for c, a in zip(self.customers, self.activity)]
        return self.rng.choices(self.customers, weights=weights, k=1)[0]

    def _pick_category(self, customer):
        if self._scenario_name() == "category_surge":
            cat = self.scenario["category"]
            if cat in customer["preferred"] and self.rng.random() < 0.8:
                return cat
        return self.rng.choices(CATEGORIES, weights=customer["category_weights"], k=1)[0]

    # ---------- building one row ----------
    def _build(self, customer, category, multiplier, anomaly_type):
        product_id, base_price = self.rng.choice(CATEGORY_PRODUCTS[category])
        unit_price = base_price * customer["spend_level"] * self.rng.lognormvariate(0, 0.08) * multiplier
        if anomaly_type is None and self._scenario_name() == "revenue_drop":
            unit_price *= 0.35
        unit_price = max(1.0, round(unit_price, 2))
        quantity = self.rng.choice(QUANTITY_CHOICES.get(category, DEFAULT_QUANTITIES))
        payment = customer["payment"] if self.rng.random() < 0.7 else \
            self.rng.choices(PAYMENT_METHODS, PAYMENT_WEIGHTS)[0]
        device = customer["device"] if self.rng.random() < 0.8 else \
            self.rng.choices(DEVICES, DEVICE_WEIGHTS)[0]
        self.counter += 1
        return {
            "transaction_id": f"TXN{self.counter:08d}",
            "txn_timestamp": self.clock.replace(microsecond=0),
            "customer_id": customer["customer_id"],
            "product_id": product_id,
            "category": category,
            "quantity": quantity,
            "unit_price": unit_price,
            "total_amount": round(quantity * unit_price, 2),
            "payment_method": payment,
            "city": customer["city"],
            "device_type": device,
            "injected_anomaly_type": anomaly_type,
        }

    def _make_anomaly(self, customer):
        atype = self.rng.choices(ANOMALY_TYPES, weights=ANOMALY_WEIGHTS, k=1)[0]
        if atype == "night_activity" and self.clock.hour not in NIGHT_HOURS:
            atype = "large_amount"
        prefs = customer["preferred"]
        category = self.rng.choice(prefs)

        if atype == "large_amount":
            return self._build(customer, category, self.rng.uniform(6, 20), atype)
        if atype == "unusual_category":
            others = [c for c in CATEGORIES if c not in prefs]
            return self._build(customer, self.rng.choice(others), self.rng.uniform(2.5, 5), atype)
        if atype == "night_activity":
            return self._build(customer, category, self.rng.uniform(3, 8), atype)
        if atype == "burst":
            for _ in range(self.rng.randint(4, 6)):
                self.pending.append({"customer": customer, "category": category,
                                     "multiplier": 1.0, "type": atype, "gap": (5, 40)})
            return self._build(customer, category, 1.0, atype)
        # spending_spike
        for _ in range(3):
            self.pending.append({"customer": customer, "category": category,
                                 "multiplier": self.rng.uniform(3, 5), "type": atype, "gap": (20, 90)})
        return self._build(customer, category, self.rng.uniform(3, 5), atype)

    # ---------- public ----------
    def next_transaction(self):
        if self.pending:
            spec = self.pending.popleft()
            self.clock += timedelta(seconds=self.rng.uniform(*spec["gap"]))
            return self._build(spec["customer"], spec["category"], spec["multiplier"], spec["type"])

        self.clock += timedelta(seconds=self._next_gap())
        self._update_scenario()
        customer = self._pick_customer()
        if self.rng.random() < self.anomaly_rate:
            return self._make_anomaly(customer)
        return self._build(customer, self._pick_category(customer), 1.0, None)


def generate_history(end_time, days, start_counter=0, anomaly_rate=None):
    """Generate `days` of past transactions ending at end_time (no waiting)."""
    gen = TransactionGenerator(end_time - timedelta(days=days), start_counter=start_counter,
                               anomaly_rate=anomaly_rate)
    rows = []
    while gen.clock < end_time:
        rows.append(gen.next_transaction())
    return rows


def run_live(anomaly_rate, interval, scenario=None):
    ok, message = database.check_connection()
    log.info(message)
    if not ok:
        return
    last_ts = database.get_latest_timestamp()
    if last_ts is None:
        log.error("No history found. Run first:  python -m src.seed_history")
        return

    gen = TransactionGenerator(last_ts, start_counter=database.get_last_txn_number(),
                               anomaly_rate=anomaly_rate)
    if scenario:
        gen.start_scenario(scenario, 120)
    log.info("Generator started (anomaly rate %.3f, one transaction every %.1fs). "
             "Press Ctrl+C to stop.", anomaly_rate, interval)
    try:
        while True:
            try:
                txn = gen.next_transaction()
                database.insert_transactions([txn])
                tag = f"  [injected: {txn['injected_anomaly_type']}]" if txn["injected_anomaly_type"] else ""
                log.info("Transaction inserted: %s | %s | %s | %s | %s%s",
                         txn["transaction_id"], txn["customer_id"], txn["category"],
                         format_inr(txn["total_amount"]), txn["city"], tag)
                for event in gen.events:
                    log.info(event)
                gen.events.clear()
            except Exception as exc:  # noqa: BLE001
                log.error("Insert failed (%s). Retrying in 5 seconds...", exc)
                time.sleep(5)
                continue
            time.sleep(interval)
    except KeyboardInterrupt:
        log.info("Generator stopped.")


def main():
    parser = argparse.ArgumentParser(description="Live transaction generator")
    parser.add_argument("--anomaly-rate", type=float, default=config.ANOMALY_RATE)
    parser.add_argument("--interval", type=float, default=config.TXN_INTERVAL_SECONDS)
    parser.add_argument("--scenario", choices=SCENARIOS, default=None,
                        help="Start a business scenario immediately (good for demos)")
    args = parser.parse_args()
    run_live(args.anomaly_rate, args.interval, args.scenario)


if __name__ == "__main__":
    main()