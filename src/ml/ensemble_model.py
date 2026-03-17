import pickle
import json
import numpy as np
from pathlib import Path
from typing import Optional, Tuple, Dict
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score, brier_score_loss
from sklearn.calibration import CalibratedClassifierCV

# Ensemble constants
RF_WEIGHT = 0.45
XGB_WEIGHT = 0.55
DISAGREEMENT_THRESHOLD = 0.15
MIN_TRAINING_SAMPLES = 200
ENSEMBLE_MODEL_PATH = Path("data/models/ensemble_model_v2.pkl")
ENSEMBLE_META_PATH = Path("data/models/ensemble_meta_v2.json")

# RF hyperparameters — tuned for NBA game prediction
RF_PARAMS = {
    "n_estimators": 400,
    "max_depth": 8,
    "min_samples_leaf": 10,
    "max_features": "sqrt",
    "class_weight": "balanced",
    "random_state": 42,
    "n_jobs": -1,
}

# XGBoost/GBM hyperparameters
XGB_PARAMS = {
    "n_estimators": 300,
    "max_depth": 5,
    "learning_rate": 0.05,
    "subsample": 0.8,
    "min_samples_leaf": 8,
    "random_state": 42,
}

def _build_xgb_model():
    """Build XGBoost if available, fall back to GradientBoosting."""
    try:
        from xgboost import XGBClassifier
        return XGBClassifier(
            n_estimators=XGB_PARAMS["n_estimators"],
            max_depth=XGB_PARAMS["max_depth"],
            learning_rate=XGB_PARAMS["learning_rate"],
            subsample=XGB_PARAMS["subsample"],
            min_child_weight=XGB_PARAMS["min_samples_leaf"],
            random_state=XGB_PARAMS["random_state"],
            eval_metric="logloss",
            verbosity=0,
            use_label_encoder=False,
        )
    except ImportError:
        print("XGBoost not available — using GradientBoostingClassifier")
        return GradientBoostingClassifier(
            n_estimators=XGB_PARAMS["n_estimators"],
            max_depth=XGB_PARAMS["max_depth"],
            learning_rate=XGB_PARAMS["learning_rate"],
            subsample=XGB_PARAMS["subsample"],
            min_samples_leaf=XGB_PARAMS["min_samples_leaf"],
            random_state=XGB_PARAMS["random_state"],
        )

def train_ensemble(
    X: np.ndarray,
    y: np.ndarray,
    test_size: float = 0.20,
) -> dict:
    """
    Train RF + XGBoost ensemble on feature matrix.
    Returns training report with AUC, Brier, disagreement stats.
    Saves model to data/models/ensemble_model.pkl.
    """
    if len(X) < MIN_TRAINING_SAMPLES:
        raise ValueError(
            f"Need at least {MIN_TRAINING_SAMPLES} samples to train ensemble. "
            f"Got {len(X)}. Run real_data_pipeline first."
        )

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=42, stratify=y
    )

    print(f"Training on {len(X_train)} samples, testing on {len(X_test)}")

    # Train RF with Platt scaling calibration
    print("Training Random Forest...")
    rf_base = RandomForestClassifier(**RF_PARAMS)
    rf_model = CalibratedClassifierCV(rf_base, method="sigmoid", cv=3)
    rf_model.fit(X_train, y_train)
    rf_probs = rf_model.predict_proba(X_test)[:, 1]
    rf_auc = roc_auc_score(y_test, rf_probs)
    rf_brier = brier_score_loss(y_test, rf_probs)
    print(f"RF: AUC={rf_auc:.4f}, Brier={rf_brier:.4f}")

    # Train XGBoost/GBM
    print("Training XGBoost/GBM...")
    xgb_base = _build_xgb_model()
    xgb_model = CalibratedClassifierCV(xgb_base, method="sigmoid", cv=3)
    xgb_model.fit(X_train, y_train)
    xgb_probs = xgb_model.predict_proba(X_test)[:, 1]
    xgb_auc = roc_auc_score(y_test, xgb_probs)
    xgb_brier = brier_score_loss(y_test, xgb_probs)
    print(f"XGB: AUC={xgb_auc:.4f}, Brier={xgb_brier:.4f}")

    # Ensemble predictions
    ensemble_probs = RF_WEIGHT * rf_probs + XGB_WEIGHT * xgb_probs
    ensemble_auc = roc_auc_score(y_test, ensemble_probs)
    ensemble_brier = brier_score_loss(y_test, ensemble_probs)
    disagreement = np.abs(rf_probs - xgb_probs)
    print(f"Ensemble: AUC={ensemble_auc:.4f}, Brier={ensemble_brier:.4f}")
    print(f"Mean model disagreement: {disagreement.mean():.4f}")

    # Validate AUC target
    if ensemble_auc < 0.837:
        print(f"WARNING: Ensemble AUC {ensemble_auc:.4f} below 0.837 minimum")
    elif ensemble_auc > 0.870:
        print(f"TARGET MET: AUC {ensemble_auc:.4f} > 0.870")

    # Save models
    ENSEMBLE_MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(ENSEMBLE_MODEL_PATH, "wb") as f:
        pickle.dump({"rf": rf_model, "xgb": xgb_model}, f)

    # Feature importance from RF
    try:
        from src.ml.feature_engineer import FEATURE_NAMES
        importances = rf_base.feature_importances_ if hasattr(rf_base, "feature_importances_") else []
        top_features = []
        if len(importances) == len(FEATURE_NAMES):
            idx = np.argsort(importances)[::-1][:10]
            top_features = [
                {"feature": FEATURE_NAMES[i], "importance": round(float(importances[i]), 4)}
                for i in idx
            ]
    except Exception:
        top_features = []

    meta = {
        "rf_auc": round(rf_auc, 4),
        "xgb_auc": round(xgb_auc, 4),
        "ensemble_auc": round(ensemble_auc, 4),
        "rf_brier": round(rf_brier, 4),
        "xgb_brier": round(xgb_brier, 4),
        "ensemble_brier": round(ensemble_brier, 4),
        "rf_weight": RF_WEIGHT,
        "xgb_weight": XGB_WEIGHT,
        "training_samples": len(X_train),
        "test_samples": len(X_test),
        "mean_disagreement": round(float(disagreement.mean()), 4),
        "high_uncertainty_rate": round(float((disagreement > DISAGREEMENT_THRESHOLD).mean()), 4),
        "top_features": top_features,
        "auc_target_met": ensemble_auc > 0.870,
        "brier_target_met": ensemble_brier < 0.180,
    }

    with open(ENSEMBLE_META_PATH, "w") as f:
        json.dump(meta, f, indent=2)

    print(f"Model saved to {ENSEMBLE_MODEL_PATH}")
    return meta

def predict_ensemble(
    X: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Run ensemble prediction on feature matrix.
    Returns (ensemble_probs, rf_probs, xgb_probs).
    Falls back to RF-only if ensemble not available.
    """
    if not ENSEMBLE_MODEL_PATH.exists():
        # Fallback to existing RF model
        rf_path = Path("data/models/win_prob_rf.pkl")
        if rf_path.exists():
            with open(rf_path, "rb") as f:
                rf_model = pickle.load(f)
            rf_probs = rf_model.predict_proba(X)[:, 1]
            return rf_probs, rf_probs, rf_probs
        return np.full(len(X), 0.57), np.full(len(X), 0.57), np.full(len(X), 0.57)

    with open(ENSEMBLE_MODEL_PATH, "rb") as f:
        models = pickle.load(f)

    rf_probs = models["rf"].predict_proba(X)[:, 1]
    xgb_probs = models["xgb"].predict_proba(X)[:, 1]
    ensemble_probs = RF_WEIGHT * rf_probs + XGB_WEIGHT * xgb_probs
    return ensemble_probs, rf_probs, xgb_probs

def predict_single_game(
    feature_vector: np.ndarray,
    is_stale: bool = False,
) -> dict:
    """
    Predict win probability for a single game feature vector.
    Returns prediction with confidence and uncertainty flag.
    """
    X = feature_vector.reshape(1, -1)
    ensemble, rf, xgb = predict_ensemble(X)
    win_prob = float(ensemble[0])
    disagreement = float(abs(rf[0] - xgb[0]))
    confidence_level = (
        "HIGH" if disagreement < 0.05
        else "MEDIUM" if disagreement < DISAGREEMENT_THRESHOLD
        else "LOW"
    )

    # Session A: Pipeline Armor — downgrade confidence if staleness detected
    if is_stale:
        if confidence_level == "HIGH":
            confidence_level = "MEDIUM"
        else:
            confidence_level = "LOW"

    # Widen confidence intervals (pseudo-CI based on disagreement and staleness)
    base_ci = 0.05 + disagreement
    if is_stale:
        base_ci /= 0.65 # CONFIDENCE_STALE_PENALTY divisor to widen

    return {
        "win_probability": round(win_prob, 4),
        "rf_probability": round(float(rf[0]), 4),
        "xgb_probability": round(float(xgb[0]), 4),
        "disagreement": round(disagreement, 4),
        "is_uncertain": disagreement > DISAGREEMENT_THRESHOLD or is_stale,
        "confidence": confidence_level,
        "ci_lower": round(max(0, win_prob - base_ci), 4),
        "ci_upper": round(min(1, win_prob + base_ci), 4),
        "is_stale": is_stale,
    }

def load_ensemble_meta() -> dict:
    """Load ensemble training metadata."""
    if not ENSEMBLE_META_PATH.exists():
        return {"status": "not_trained"}
    with open(ENSEMBLE_META_PATH) as f:
        return json.load(f)
