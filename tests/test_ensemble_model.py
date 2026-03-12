import pytest
import numpy as np
from src.ml.ensemble_model import (
    train_ensemble,
    predict_single_game,
    MIN_TRAINING_SAMPLES,
)

def test_train_ensemble_insufficient_data():
    X = np.random.rand(10, 42)
    y = np.random.randint(0, 2, 10)
    with pytest.raises(ValueError, match="Need at least"):
        train_ensemble(X, y)

def test_train_and_predict_flow(tmp_path):
    # Mock paths
    import src.ml.ensemble_model as em
    em.ENSEMBLE_MODEL_PATH = tmp_path / "model.pkl"
    em.ENSEMBLE_META_PATH = tmp_path / "meta.json"
    
    # Generate synthetic data that is easy to separate
    X = np.random.rand(MIN_TRAINING_SAMPLES + 50, 42)
    # Make feature 0 predictive
    y = (X[:, 0] > 0.5).astype(int)
    
    meta = train_ensemble(X, y)
    assert "ensemble_auc" in meta
    assert meta["ensemble_auc"] > 0.5
    
    # Test predict
    test_vec = np.zeros(42)
    test_vec[0] = 0.9
    pred = predict_single_game(test_vec)
    assert "win_probability" in pred
    assert "is_uncertain" in pred
    assert 0 <= pred["win_probability"] <= 1.0
