import pytest
import numpy as np
from src.ml.feature_engineer import (
    engineer_features,
    build_feature_matrix,
    FEATURE_DIM,
    HOME_COURT_ADVANTAGE_PRIOR,
)

def test_engineer_features_no_history():
    log = {
        "home_team": "BOS",
        "away_team": "NYK",
        "game_date": "2024-01-01",
        "home_ortg": 115.0,
        "home_drtg": 105.0,
        "away_ortg": 110.0,
        "away_drtg": 110.0,
        "home_rest_days": 2,
        "away_rest_days": 1,
        "home_is_b2b": False,
        "away_is_b2b": True,
        "home_altitude_ft": 141,
        "away_altitude_ft": 33,
    }
    vec = engineer_features(log, [], causal_wp_adjustment=0.05)
    
    assert len(vec) == FEATURE_DIM
    # Group A: Quality
    assert vec[0] == 115.0 / 120.0
    assert vec[1] == 110.0 / 120.0
    assert vec[4] == (115.0 - 105.0) / 20.0 # home net rtg
    
    # Group B: Rest
    assert vec[8] == 2 / 7.0
    assert vec[9] == 1 / 7.0
    assert vec[10] == 0.0
    assert vec[11] == 1.0
    
    # Group C: Venue
    assert vec[20] == HOME_COURT_ADVANTAGE_PRIOR
    
    # Group F: Causal
    assert vec[38] == 0.05

def test_build_feature_matrix():
    logs = [
        {"home_team": "BOS", "home_win": 1, "home_ortg": 115.0},
        {"home_team": "NYK", "home_win": 0, "home_ortg": 110.0},
    ]
    X, y = build_feature_matrix(logs)
    assert X.shape == (2, FEATURE_DIM)
    assert y.shape == (2,)
    assert y[0] == 1.0
    assert y[1] == 0.0
