import sys
from pathlib import Path
import numpy as np
import json
import logging

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.intelligence.win_probability import WinProbabilityModel

def test_base_model():
    model = WinProbabilityModel()
    model.TRAIN_DATA = Path("data/real/games_2024.jsonl")
    
    print(f"Testing WinProbabilityModel on {model.TRAIN_DATA}")
    
    if not model.TRAIN_DATA.exists():
        print("Data file not found.")
        return
        
    class DummyState:
        def __init__(self, d):
            self.quarter = d["quarter"]
            self.clock = d["clock"]
            self.home_score = d["home_score"]
            self.away_score = d["away_score"]

    with open(model.TRAIN_DATA, "r") as f:
        games_iter = [json.loads(line) for line in f]
        X, y = model._process_games(games_iter, model, DummyState)
        
    if len(X) == 0:
        print("No test data found.")
        return
        
    print(f"Evaluating on {len(X)} snapshots...")
    X_arr = np.array(X, dtype=np.float32)
    y_arr = np.array(y, dtype=np.int8)
    
    # Reload model
    import joblib
    rf = joblib.load(model.MODEL_PATH)
    preds = rf.predict_proba(X_arr)[:, 1]
    
    from sklearn.metrics import roc_auc_score, brier_score_loss
    auc = roc_auc_score(y_arr, preds)
    brier = brier_score_loss(y_arr, preds)
    
    print(f"Base Model AUC: {auc:.4f}")
    print(f"Base Model Brier: {brier:.4f}")

if __name__ == "__main__":
    test_base_model()
