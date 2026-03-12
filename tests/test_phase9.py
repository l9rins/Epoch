import pytest
import os
import json
from pathlib import Path
from src.intelligence.pregame_predictor import PregamePredictor
from src.ml.calibration import CalibrationEngine

@pytest.fixture
def predictor():
    return PregamePredictor()

def test_pregame_prediction_valid_range(predictor):
    # Test with Warriors and Lakers (data should exist from Phase 8)
    pred = predictor.predict("GSW", "LAL")
    assert 0.20 <= pred["predicted_home_win_prob"] <= 0.80
    assert "game_id" in pred
    assert pred["home_team"] == "GSW"
    assert pred["away_team"] == "LAL"

def test_prediction_logged_to_file(predictor):
    pred = predictor.predict("GSW", "LAL")
    predictor.log_prediction(pred)
    
    from datetime import datetime
    date_str = datetime.now().strftime("%Y-%m-%d")
    log_file = Path("data/predictions") / f"{date_str}.jsonl"
    
    assert log_file.exists()
    lines = log_file.read_text().splitlines()
    last_pred = json.loads(lines[-1])
    assert last_pred["game_id"] == pred["game_id"]

def test_result_recording(predictor):
    # 1. Create a prediction
    pred = predictor.predict("GSW", "LAL")
    predictor.log_prediction(pred)
    game_id = pred["game_id"]
    
    # 2. Record result
    cal = CalibrationEngine()
    initial_count = cal.report()["games_tracked"]
    
    updated_pred = predictor.record_result(game_id, 110, 100)
    
    assert updated_pred is not None
    assert updated_pred["actual_home_score"] == 110
    assert updated_pred["actual_away_score"] == 100
    assert updated_pred["actual_winner"] == "HOME"
    
    # Check calibration engine updated
    final_count = cal.report()["games_tracked"]
    assert final_count == initial_count + 1

def test_team_strength_handling_missing_data(predictor):
    # Test with non-existent team
    strength = predictor._get_team_strength("XYZ")
    assert strength == 50.0 # Baseline for missing data
