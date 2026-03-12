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
    assert prob < 0.25

def test_momentum_scoring_run():
    tracker = MomentumTracker()
    tracker(GameState(timestamp=0, quarter=1, clock=600.0, home_score=0, away_score=0, possession=0))
    momentum = tracker(GameState(timestamp=30, quarter=1, clock=570.0, home_score=10, away_score=0, possession=0))
    assert momentum > 60

def test_alert_threshold_fires():
    engine = AlertEngine()  # No log_dir = no filesystem side effects

    # Start at 50%
    engine.process(game_time=0.0, win_prob=0.50, momentum=0.0, proj_home=100, proj_away=100)

    # Jump to 76% (crosses 75% boundary)
    alerts = engine.process(game_time=10.0, win_prob=0.76, momentum=0.0, proj_home=110, proj_away=90)
    threshold_alerts = [a for a in alerts if a.alert_type == "WIN_PROB_THRESHOLD"]

    assert len(threshold_alerts) > 0
    assert any("75%" in a.message for a in threshold_alerts)
    # 75% boundary → Tier 2
    assert threshold_alerts[0].tier == 2

def test_alert_no_duplicate():
    engine = AlertEngine()

    # Cross 75%
    engine.process(game_time=0.0, win_prob=0.50, momentum=0.0, proj_home=100, proj_away=100)
    alerts1 = engine.process(game_time=10.0, win_prob=0.76, momentum=0.0, proj_home=110, proj_away=90)
    assert any(a.alert_type == "WIN_PROB_THRESHOLD" for a in alerts1)

    # Stay above 75% but fluctuate — no duplicate
    alerts2 = engine.process(game_time=20.0, win_prob=0.78, momentum=0.0, proj_home=110, proj_away=90)
    alerts3 = engine.process(game_time=30.0, win_prob=0.89, momentum=0.0, proj_home=110, proj_away=90)

    assert not any(a.alert_type == "WIN_PROB_THRESHOLD" for a in alerts2)
    assert not any(a.alert_type == "WIN_PROB_THRESHOLD" for a in alerts3)

def test_alert_threshold_90_is_tier_1():
    """Crossing the 90% boundary should produce a Tier 1 (critical) alert."""
    engine = AlertEngine()

    engine.process(game_time=0.0, win_prob=0.80, momentum=0.0, proj_home=100, proj_away=100)
    alerts = engine.process(game_time=100.0, win_prob=0.92, momentum=0.0, proj_home=115, proj_away=90)
    threshold_alerts = [a for a in alerts if a.alert_type == "WIN_PROB_THRESHOLD"]

    assert len(threshold_alerts) == 1
    assert threshold_alerts[0].tier == 1
    assert "90%" in threshold_alerts[0].message

def test_momentum_shift_fires_on_big_swing():
    engine = AlertEngine()

    # Build a >30 swing inside 60 seconds
    engine.process(game_time=0.0, win_prob=0.5, momentum=-10.0, proj_home=100, proj_away=100)
    alerts = engine.process(game_time=30.0, win_prob=0.5, momentum=25.0, proj_home=100, proj_away=100)

    mom_alerts = [a for a in alerts if a.alert_type == "MOMENTUM_SHIFT"]
    assert len(mom_alerts) == 1
    assert "HOME" in mom_alerts[0].message  # momentum > 0 → HOME direction

def test_momentum_cooldown_prevents_spam():
    engine = AlertEngine()

    # First swing fires at t=30 (swing from -20 to +15 = 35 > 30)
    engine.process(game_time=0.0, win_prob=0.5, momentum=-20.0, proj_home=100, proj_away=100)
    alerts1 = engine.process(game_time=30.0, win_prob=0.5, momentum=15.0, proj_home=100, proj_away=100)
    assert any(a.alert_type == "MOMENTUM_SHIFT" for a in alerts1)

    # Second swing within cooldown (90s from t=30) should NOT fire
    engine.process(game_time=60.0, win_prob=0.5, momentum=-20.0, proj_home=100, proj_away=100)
    alerts2 = engine.process(game_time=90.0, win_prob=0.5, momentum=15.0, proj_home=100, proj_away=100)
    assert not any(a.alert_type == "MOMENTUM_SHIFT" for a in alerts2)

    # Well after cooldown (t=250, 250-30=220 > 90), it should fire again
    engine.process(game_time=250.0, win_prob=0.5, momentum=-20.0, proj_home=100, proj_away=100)
    alerts3 = engine.process(game_time=280.0, win_prob=0.5, momentum=15.0, proj_home=100, proj_away=100)
    assert any(a.alert_type == "MOMENTUM_SHIFT" for a in alerts3)

def test_projection_only_fires_on_change():
    engine = AlertEngine()

    # First call always fires
    alerts1 = engine.process(game_time=0.0, win_prob=0.5, momentum=0.0, proj_home=100, proj_away=100)
    assert any(a.alert_type == "PROJECTION_UPDATE" for a in alerts1)

    # Same projection after 120s — should NOT fire
    alerts2 = engine.process(game_time=130.0, win_prob=0.5, momentum=0.0, proj_home=100, proj_away=100)
    assert not any(a.alert_type == "PROJECTION_UPDATE" for a in alerts2)

    # Changed projection after 120s — SHOULD fire
    alerts3 = engine.process(game_time=260.0, win_prob=0.5, momentum=0.0, proj_home=108, proj_away=95)
    assert any(a.alert_type == "PROJECTION_UPDATE" for a in alerts3)

def test_alert_direction_indicator():
    """Win prob alerts should include ↑ or ↓ direction."""
    engine = AlertEngine()

    engine.process(game_time=0.0, win_prob=0.50, momentum=0.0, proj_home=100, proj_away=100)
    alerts = engine.process(game_time=10.0, win_prob=0.76, momentum=0.0, proj_home=110, proj_away=90)
    threshold_alerts = [a for a in alerts if a.alert_type == "WIN_PROB_THRESHOLD"]

    assert len(threshold_alerts) > 0
    assert "↑" in threshold_alerts[0].message
