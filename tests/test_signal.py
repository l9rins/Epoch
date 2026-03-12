import pytest
from src.simulation.memory_reader import GameState
from src.intelligence.win_probability import WinProbabilityModel
from src.intelligence.momentum import MomentumTracker
from src.intelligence.signal_alerts import AlertEngine

def test_win_prob_at_tipoff():
    model = WinProbabilityModel()
    state = GameState(timestamp=0, quarter=1, clock=720.0, home_score=0, away_score=0, possession=0)
    prob = model(state)
    assert 0.45 < prob < 0.55

def test_win_prob_large_lead():
    model = WinProbabilityModel()
    state = GameState(timestamp=0, quarter=4, clock=120.0, home_score=110, away_score=90, possession=0)
    prob = model(state)
    assert prob > 0.90

def test_win_prob_losing_big():
    model = WinProbabilityModel()
    state = GameState(timestamp=0, quarter=4, clock=120.0, home_score=90, away_score=110, possession=0)
    prob = model(state)
    assert prob < 0.10

def test_momentum_scoring_run():
    tracker = MomentumTracker()
    # Initial state
    tracker(GameState(timestamp=0, quarter=1, clock=600.0, home_score=0, away_score=0, possession=0))
    # 10 unanswered points in 30 seconds
    momentum = tracker(GameState(timestamp=30, quarter=1, clock=570.0, home_score=10, away_score=0, possession=0))
    # decay over 30 seconds is 0.9^30 ~ 0.04... Wait, 10 points * 10 * 0.9^0 = 100.
    # Ah, the decay is relative to the current time! So 0.9^0 is 1. The age of the event is 0 (relative to the last state).
    # Momentum should be exactly 100 initially.
    assert momentum > 60

def test_alert_threshold_fires():
    engine = AlertEngine()
    
    # Start at 50%
    engine.process(game_time=0.0, win_prob=0.50, momentum=0.0, proj_home=100, proj_away=100)
    
    # Jump to 76% (crosses 60% and 75%)
    alerts = engine.process(game_time=10.0, win_prob=0.76, momentum=0.0, proj_home=110, proj_away=90)
    threshold_alerts = [a for a in alerts if a.alert_type == "WIN_PROB_THRESHOLD"]
    
    assert len(threshold_alerts) > 0
    assert any("75%" in a.message for a in threshold_alerts)

def test_alert_no_duplicate():
    engine = AlertEngine()
    
    # Cross 75%
    engine.process(game_time=0.0, win_prob=0.50, momentum=0.0, proj_home=100, proj_away=100)
    alerts1 = engine.process(game_time=10.0, win_prob=0.76, momentum=0.0, proj_home=110, proj_away=90)
    assert any(a.alert_type == "WIN_PROB_THRESHOLD" for a in alerts1)
    
    # Stay above 75% but fluctuate
    alerts2 = engine.process(game_time=20.0, win_prob=0.78, momentum=0.0, proj_home=110, proj_away=90)
    alerts3 = engine.process(game_time=30.0, win_prob=0.89, momentum=0.0, proj_home=110, proj_away=90)
    
    assert not any(a.alert_type == "WIN_PROB_THRESHOLD" for a in alerts2)
    assert not any(a.alert_type == "WIN_PROB_THRESHOLD" for a in alerts3)
