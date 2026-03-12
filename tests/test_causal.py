from src.intelligence.causal_dag import (
    run_causal_inference, CausalNode, CausalState,
    propagate_causal_effects, compute_win_probability_adjustment
)

def test_no_intervention_neutral():
    result = run_causal_inference()
    assert abs(result.win_probability_adjustment) < 0.01

def test_star_injury_hurts_team():
    result = run_causal_inference(
        away_interventions={CausalNode.PLAYER_HEALTH: 0.3}
    )
    assert result.win_probability_adjustment > 0.0

def test_both_injured_roughly_neutral():
    result = run_causal_inference(
        home_interventions={CausalNode.PLAYER_HEALTH: 0.3},
        away_interventions={CausalNode.PLAYER_HEALTH: 0.3},
    )
    assert abs(result.win_probability_adjustment) < 0.05

def test_causal_chain_populated():
    result = run_causal_inference(
        home_interventions={CausalNode.PLAYER_HEALTH: 0.5}
    )
    assert len(result.causal_chain) > 0

def test_confidence_increases_with_interventions():
    low = run_causal_inference()
    high = run_causal_inference(
        home_interventions={CausalNode.PLAYER_HEALTH: 0.4},
        away_interventions={CausalNode.PLAYER_HEALTH: 0.8},
    )
    assert high.confidence > low.confidence
