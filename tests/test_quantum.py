from src.simulation.quantum_roster import (
    _build_synthetic_quantum_roster,
    run_quantum_monte_carlo,
    PlayerPerformanceDistribution,
    QuantumRoster,
    ARCHETYPE_DISTRIBUTIONS,
)
import numpy as np

def test_quantum_roster_builds():
    roster = _build_synthetic_quantum_roster("GSW")
    assert len(roster.players) > 0
    assert roster.team_abbr == "GSW"

def test_sample_lineup_returns_all_players():
    roster = _build_synthetic_quantum_roster("LAL")
    rng = np.random.default_rng(42)
    sample = roster.sample_lineup(rng)
    assert len(sample["player_samples"]) == len(roster.players)

def test_night_types_valid():
    roster = _build_synthetic_quantum_roster("BOS")
    rng = np.random.default_rng(0)
    valid_types = set(["cold", "below_avg", "average", "above_avg", "hot"])
    for _ in range(20):
        sample = roster.sample_lineup(rng)
        for ps in sample["player_samples"].values():
            assert ps["night_type"] in valid_types

def test_monte_carlo_win_prob_range():
    home = _build_synthetic_quantum_roster("GSW")
    away = _build_synthetic_quantum_roster("LAL")
    result = run_quantum_monte_carlo(home, away, n_iterations=200, seed=42)
    assert 0.0 <= result["win_probability"] <= 1.0

def test_monte_carlo_confidence_interval():
    home = _build_synthetic_quantum_roster("MIA")
    away = _build_synthetic_quantum_roster("BOS")
    result = run_quantum_monte_carlo(home, away, n_iterations=200, seed=1)
    ci = result["confidence_interval_80pct"]
    assert ci[0] <= ci[1]

def test_variance_profile_valid():
    home = _build_synthetic_quantum_roster("DEN")
    away = _build_synthetic_quantum_roster("PHX")
    result = run_quantum_monte_carlo(home, away, n_iterations=200, seed=7)
    assert result["variance_profile"] in ["LOW", "MEDIUM", "HIGH"]

def test_different_seeds_different_results():
    home = _build_synthetic_quantum_roster("GSW")
    away = _build_synthetic_quantum_roster("LAL")
    r1 = run_quantum_monte_carlo(home, away, n_iterations=100, seed=1)
    r2 = run_quantum_monte_carlo(home, away, n_iterations=100, seed=2)
    assert r1["win_probability"] != r2["win_probability"]
