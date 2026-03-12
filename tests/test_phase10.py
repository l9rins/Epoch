import pytest
import numpy as np
from pathlib import Path
from src.intelligence.fatigue_model import FatigueModel
from src.pipeline.results_ingestion import ResultsIngestion
from src.intelligence.win_probability import WinProbabilityModel
from src.simulation.memory_reader import GameState

@pytest.fixture
def f_model():
    return FatigueModel()

@pytest.fixture
def wp_model():
    return WinProbabilityModel()

def test_fatigue_q4_lower_than_q1(f_model):
    q1 = f_model.get_fatigue_factor(1, False)
    q4 = f_model.get_fatigue_factor(4, False)
    assert q4 < q1
    assert q1 == 1.0
    assert q4 == 0.90

def test_back_to_back_penalty(f_model):
    fresh = f_model.get_fatigue_factor(1, False)
    tired = f_model.get_fatigue_factor(1, True)
    assert tired < fresh
    assert abs(fresh - tired - 0.05) < 0.001

def test_fatigue_adjusts_win_prob(f_model):
    base_prob = 0.50
    # Home is tired (0.85), Away is fresh (1.0)
    # fatigue_diff = -0.15 -> adjustment = -0.015
    adjusted = f_model.adjust_win_probability(base_prob, 0.85, 1.0)
    assert adjusted < base_prob
    assert adjusted == 0.485

def test_vision_bridge_enriches_state(wp_model):
    import time
    state = GameState(
        timestamp=time.time(),
        quarter=1,
        clock=600.0,
        home_score=20,
        away_score=10,
        possession=0
    )
    intelligence = {
        "defensive_spacing": 75.5,
        "paint_density": 8.1,
        "three_point_coverage": 40.0,
        "pick_roll": 1,
        "fast_break": 0,
        "open_shooter": 1,
        "fatigue_home": 0.95,
        "fatigue_away": 1.0
    }
    
    features = wp_model._extract_features(state, extra_features=intelligence)
    assert len(features) == 14
    assert features[6] == 75.5 # spacing
    assert features[11] == 1 # open_shooter
    assert features[12] == 0.95 # fatigue_home

def test_retrained_model_auc(wp_model):
    import json
    from pathlib import Path
    meta_file = Path("data/models/win_prob_meta.json")
    if not meta_file.exists():
        pytest.skip("Model not trained yet")
    meta = json.loads(meta_file.read_text())
    assert "auc" in meta
    assert meta["auc"] > 0.80, f"Validation AUC {meta['auc']} below target 0.80"

def test_results_ingestion_structure():
    ingestor = ResultsIngestion()
    assert hasattr(ingestor, 'ingest_yesterday')
    assert hasattr(ingestor, 'run_daily')
