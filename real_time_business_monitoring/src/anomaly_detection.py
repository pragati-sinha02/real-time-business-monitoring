"""Z-score baseline + Isolation Forest."""
from datetime import datetime

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

from . import config
from .feature_engineering import FEATURE_COLUMNS, get_model_matrix


def train_isolation_forest(features: pd.DataFrame, contamination: float = None,
                           n_estimators: int = 200, random_state: int = 42) -> dict:
    """Train the model and return a 'bundle' (model + settings) that can be saved."""
    contamination = config.CONTAMINATION if contamination is None else contamination
    X = get_model_matrix(features)

    model = IsolationForest(n_estimators=n_estimators, contamination=contamination,
                            random_state=random_state, n_jobs=1)
    model.fit(X)

    raw = model.score_samples(X)  # higher = more normal, lower = more anomalous
    return {
        "model": model,
        "features": list(FEATURE_COLUMNS),
        "score_typical": float(np.percentile(raw, 50)),   # a typical, normal transaction
        "score_extreme": float(np.percentile(raw, 0.5)),  # among the most anomalous 0.5%
        "contamination": contamination,
        "n_rows": int(len(X)),
        "trained_at": datetime.now().isoformat(timespec="seconds"),
    }


def save_bundle(bundle: dict, path=config.MODEL_PATH) -> None:
    path.parent.mkdir(exist_ok=True)
    joblib.dump(bundle, path)


def load_bundle(path=config.MODEL_PATH) -> dict:
    if not path.exists():
        raise FileNotFoundError(
            f"Model file not found: {path}\nTrain it first with:  python -m src.train_model")
    return joblib.load(path)


def score_transactions(features: pd.DataFrame, bundle: dict,
                       z_threshold: float = None) -> pd.DataFrame:
    """Adds z_score, z_flag, iso_score, iso_flag, is_anomaly columns."""
    z_threshold = config.Z_THRESHOLD if z_threshold is None else z_threshold
    out = features.copy()
    X = get_model_matrix(out)[bundle["features"]]

    out["z_score"] = out["amount_zscore"]
    out["z_flag"] = (out["z_score"].abs() >= z_threshold).astype(int)
    out["iso_score"] = bundle["model"].score_samples(X)
    out["iso_flag"] = (bundle["model"].predict(X) == -1).astype(int)   # -1 means anomaly
    out["is_anomaly"] = ((out["z_flag"] == 1) | (out["iso_flag"] == 1)).astype(int)
    return out