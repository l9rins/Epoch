import pytest
from src.intelligence.causal_learner import (
    learn_health_to_ortg_weight,
    learn_all_causal_weights,
    DEFAULT_CAUSAL_WEIGHTS,
)

def test_learn_health_to_ortg_weight_insufficient_data():
    logs = [{"player_ortg_impact": -5.0, "team_ortg_before": 110.0, "team_ortg_after": 105.0}]
    weight, r2 = learn_health_to_ortg_weight(logs)
    assert weight == DEFAULT_CAUSAL_WEIGHTS["PLAYER_HEALTH_to_OFFENSIVE_RATING"]
    assert r2 == 0.0

def test_learn_all_causal_weights_synthetic():
    # Generate perfect linear synthetic data
    logs = []
    for _ in range(30): # > MIN_INJURY_SAMPLES
        # Base impact
        impact = -6.0
        health_delta = impact / 20.0
        # Perfect linear drop in ORtg: ortg_delta = weight * health_delta
        # Let's target a weight of 0.8
        ortg_delta = 0.8 * health_delta
        ortg_before = 110.0
        ortg_after = ortg_before * (1 + ortg_delta)
        
        logs.append({
            "player_ortg_impact": impact,
            "team_ortg_before": ortg_before,
            "team_ortg_after": ortg_after,
            "player_usage_rate": 0.30,
            "win_probability_delta": -0.10,
        })
        
    result = learn_all_causal_weights(logs)
    assert "weights" in result
    assert result["weights"]["PLAYER_HEALTH_to_OFFENSIVE_RATING"] > 0.6
    assert result["r2_scores"]["PLAYER_HEALTH_to_OFFENSIVE_RATING"] > 0.8
