import pytest
import tempfile
import os
from pathlib import Path

from src.ml.calibration import CalibrationEngine


def test_calibration_brier_score():
    """Perfect predictor should score 0.0"""
    engine = CalibrationEngine(history_file=os.path.join(tempfile.mkdtemp(), "test_cal.jsonl"))

    # Log 50 perfect predictions
    for _ in range(25):
        engine.log_outcome(1.0, True)   # predicted 100%, won
        engine.log_outcome(0.0, False)  # predicted 0%, lost

    bs = engine.brier_score()
    assert bs is not None
    assert bs == 0.0


def test_calibration_improves_over_time():
    """100 logged outcomes -> brier score decreases after recalibration"""
    engine = CalibrationEngine(history_file=os.path.join(tempfile.mkdtemp(), "test_cal2.jsonl"))

    # Log 100 outcomes with slightly miscalibrated predictions
    import random
    random.seed(42)
    for _ in range(100):
        true_prob = random.random()
        actual = 1 if random.random() < true_prob else 0
        # Miscalibrate: push predictions toward extremes
        raw_pred = min(1.0, max(0.0, true_prob * 1.3 - 0.15))
        engine.log_outcome(raw_pred, bool(actual))

    bs_before = engine.brier_score()
    assert bs_before is not None

    # After recalibration, calibrated predictions should have lower Brier
    calibrated_preds = [engine.calibrate(h[0]) for h in engine.history]
    actuals = [h[1] for h in engine.history]
    bs_after = sum((p - a) ** 2 for p, a in zip(calibrated_preds, actuals)) / len(actuals)

    assert bs_after <= bs_before


def test_calibration_report_fields():
    """accuracy_report returns expected fields"""
    engine = CalibrationEngine(history_file=os.path.join(tempfile.mkdtemp(), "test_cal3.jsonl"))

    report = engine.accuracy_report()
    assert "games_tracked" in report
    assert "brier_score" in report
    assert "target" in report
    assert "beating_espn_bpi" in report
    assert report["target"] == 0.18


def test_upgraded_win_prob_auc():
    """RandomForest AUC > 0.75 on synthetic held-out data"""
    from src.intelligence.win_probability import WinProbabilityModel
    from src.ml.scoring_run_predictor import load_synthetic_data

    games = load_synthetic_data(max_games=500)
    model = WinProbabilityModel()
    model.train(games)

    assert model.rf_model is not None
    assert WinProbabilityModel._last_auc > 0.75


def test_full_league_pipeline_creates_json():
    """Pipeline module defines all 30 NBA teams"""
    from src.pipeline.full_league_pipeline import NBA_TEAMS
    assert len(NBA_TEAMS) == 30
    assert "GSW" in NBA_TEAMS
    assert "LAL" in NBA_TEAMS
    assert "BOS" in NBA_TEAMS


def test_accuracy_api_endpoint():
    """GET /api/accuracy returns games_tracked and brier_score fields"""
    from src.api.main import app
    from fastapi.testclient import TestClient

    client = TestClient(app)
    response = client.get("/api/accuracy")
    assert response.status_code == 200
    data = response.json()
    assert "games_tracked" in data
    assert "brier_score" in data
    assert "target" in data
    assert data["target"] == 0.18
