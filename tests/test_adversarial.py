from src.intelligence.adversarial_network import (
    build_adversarial_system,
    generate_synthetic_training_games,
    run_adversarial_training_cycle,
    GameFeatures,
)

def test_oracle_predict_range():
    oracle, _, _ = build_adversarial_system()
    features = GameFeatures(
        home_win_pct=0.6, away_win_pct=0.4,
        home_rest_days=3, away_rest_days=1,
        home_ortg=115, away_ortg=108,
        home_drtg=108, away_drtg=114,
        momentum_home=0.7, momentum_away=0.4,
        pace_differential=2.0,
        injury_impact_home=0.0, injury_impact_away=0.3,
        referee_foul_rate=1.0,
        is_back_to_back_home=0.0, is_back_to_back_away=1.0,
    )
    pred = oracle.predict(features)
    assert 0.05 <= pred <= 0.95

def test_injury_reduces_win_probability():
    oracle, _, _ = build_adversarial_system()
    healthy = GameFeatures(
        home_win_pct=0.5, away_win_pct=0.5,
        home_rest_days=3, away_rest_days=3,
        home_ortg=112, away_ortg=112,
        home_drtg=110, away_drtg=110,
        momentum_home=0.5, momentum_away=0.5,
        pace_differential=0.0,
        injury_impact_home=0.0, injury_impact_away=0.0,
        referee_foul_rate=1.0,
        is_back_to_back_home=0.0, is_back_to_back_away=0.0,
    )
    injured = GameFeatures(
        **{**healthy.__dict__, "injury_impact_home": 0.8}
    )
    assert oracle.predict(healthy) > oracle.predict(injured)

def test_adversarial_training_completes():
    oracle, adversary, market = build_adversarial_system()
    games = generate_synthetic_training_games(50)
    result = run_adversarial_training_cycle(oracle, adversary, market, games, cycles=10)
    assert result["cycles_completed"] == 10
    assert "top_blind_spots" in result
    assert "market_report" in result

def test_market_efficiency_increases():
    oracle, adversary, market = build_adversarial_system()
    initial_efficiency = market.market_efficiency
    games = generate_synthetic_training_games(100)
    run_adversarial_training_cycle(oracle, adversary, market, games, cycles=20)
    assert market.market_efficiency >= initial_efficiency
