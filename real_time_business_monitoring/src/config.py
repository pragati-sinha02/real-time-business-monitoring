"""Central configuration. Values come from the .env file, with safe defaults."""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env", override=True)


def _int(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)))


def _float(name: str, default: float) -> float:
    return float(os.getenv(name, str(default)))


# ---- Database ----
DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = _int("DB_PORT", 3307)
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "Pug@123")
DB_NAME = os.getenv("DB_NAME", "business_monitor")

# ---- Generator ----
ANOMALY_RATE = _float("ANOMALY_RATE", 0.02)           # chance a new anomaly EVENT starts
TXN_INTERVAL_SECONDS = _float("TXN_INTERVAL_SECONDS", 1.0)  # real seconds between inserts
SIM_BASE_GAP_SECONDS = _float("SIM_BASE_GAP_SECONDS", 30)   # simulated seconds between txns
N_CUSTOMERS = _int("N_CUSTOMERS", 300)
SCENARIO_RATE = _float("SCENARIO_RATE", 0.001)        # chance a business scenario starts
HISTORY_DAYS = _int("HISTORY_DAYS", 7)
_seed = os.getenv("RANDOM_SEED", "").strip()
RANDOM_SEED = int(_seed) if _seed else None

# ---- Detection ----
CONTAMINATION = _float("CONTAMINATION", 0.02)
Z_THRESHOLD = _float("Z_THRESHOLD", 3.0)
PIPELINE_INTERVAL_SECONDS = _float("PIPELINE_INTERVAL_SECONDS", 5)
LOOKBACK_HOURS = _int("LOOKBACK_HOURS", 168)
ALERT_RISK_THRESHOLD = _int("ALERT_RISK_THRESHOLD", 61)   # High and above
ALERT_WINDOW_HOURS = _int("ALERT_WINDOW_HOURS", 3)

# ---- Business KPI rules (actual / expected) ----
BIZ_LOW_RATIO = 0.60
BIZ_CRITICAL_LOW_RATIO = 0.40
BIZ_HIGH_RATIO = 1.60
CATEGORY_SURGE_RATIO = 2.0
CATEGORY_DROP_RATIO = 0.40

# ---- Paths ----
MODEL_PATH = BASE_DIR / "models" / "isolation_forest.joblib"
LOG_DIR = BASE_DIR / "logs"