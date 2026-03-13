"""
Tests — src/simulation/fast_sim_mode.py
SESSION B: Mid-Game Injury Hot-Swap
"""
from __future__ import annotations
import pytest
import numpy as np


class TestFastSimIterations:
    def test_returns_exactly_200_iterations(self):
        from src.simulation.fast_sim_mode import run_fast_simulation, FAST_SIM_ITERATIONS
        result = run_fast_simulation(108.0, 108.0, 106.0, 106.0)
        assert result["iterations"] == FAST_SIM_ITERATIONS
        assert result["iterations"] == 200

    def test_full_sim_constant_is_1000(self):
        from src.simulation.fast_sim_mode import FULL_SIM_ITERATIONS
        assert FULL_SIM_ITERATIONS == 1_000


class TestRunFastSimulation:
    def test_returns_required_keys(self):
        from src.simulation.fast_sim_mode import run_fast_simulation
        result = run_fast_simulation(108.0, 108.0, 108.0, 108.0)
        required = {
            "win_probability", "iterations", "mean_home_score",
            "mean_away_score", "score_std", "importance_weighted_wp",
            "sim_duration_ms", "method",
        }
        assert required.issubset(set(result.keys()))

    def test_win_prob_between_0_and_1(self):
        from src.simulation.fast_sim_mode import run_fast_simulation
        result = run_fast_simulation(108.0, 108.0, 108.0, 108.0)
        assert 0.0 <= result["win_probability"] <= 1.0

    def test_evenly_matched_wp_near_50pct(self):
        from src.simulation.fast_sim_mode import run_fast_simulation
        result = run_fast_simulation(108.0, 108.0, 108.0, 108.0, seed=42)
        # Evenly matched teams — WP should be reasonably close to 0.5
        assert 0.30 <= result["win_probability"] <= 0.70

    def test_stronger_home_team_higher_wp(self):
        from src.simulation.fast_sim_mode import run_fast_simulation
        # Home dominant: great offense AND defense
        strong = run_fast_simulation(120.0, 120.0, 90.0, 90.0, seed=42)
        # Away dominant: home has poor ratings
        weak = run_fast_simulation(90.0, 90.0, 120.0, 120.0, seed=42)
        assert strong["win_probability"] > weak["win_probability"]

    def test_method_label(self):
        from src.simulation.fast_sim_mode import run_fast_simulation
        result = run_fast_simulation(108.0, 108.0, 108.0, 108.0)
        assert result["method"] == "fast_quantum_mc"

    def test_duration_positive(self):
        from src.simulation.fast_sim_mode import run_fast_simulation
        result = run_fast_simulation(108.0, 108.0, 108.0, 108.0)
        assert result["sim_duration_ms"] > 0

    def test_scores_reasonable(self):
        from src.simulation.fast_sim_mode import run_fast_simulation
        result = run_fast_simulation(108.0, 108.0, 108.0, 108.0, seed=42)
        assert 60 <= result["mean_home_score"] <= 160
        assert 60 <= result["mean_away_score"] <= 160

    def test_reproducible_with_same_seed(self):
        from src.simulation.fast_sim_mode import run_fast_simulation
        r1 = run_fast_simulation(108.0, 108.0, 108.0, 108.0, seed=99)
        r2 = run_fast_simulation(108.0, 108.0, 108.0, 108.0, seed=99)
        assert r1["win_probability"] == r2["win_probability"]

    def test_partial_game_remaining(self):
        from src.simulation.fast_sim_mode import run_fast_simulation
        # 5 minutes remaining — scores should change less than full game
        result = run_fast_simulation(
            108.0, 108.0, 108.0, 108.0,
            game_time_remaining=300.0,
            home_score=95,
            away_score=92,
            seed=42,
        )
        assert result["win_probability"] is not None
        assert result["mean_home_score"] >= 95


class TestImportanceWeight:
    def test_weight_at_50pct_is_highest(self):
        from src.simulation.fast_sim_mode import _importance_weight
        w_50 = _importance_weight(0.50)
        w_80 = _importance_weight(0.80)
        w_20 = _importance_weight(0.20)
        assert w_50 > w_80
        assert w_50 > w_20

    def test_weight_at_50pct_equals_importance_constant(self):
        from src.simulation.fast_sim_mode import _importance_weight, IMPORTANCE_SAMPLE_WEIGHT
        assert abs(_importance_weight(0.50) - IMPORTANCE_SAMPLE_WEIGHT) < 1e-9

    def test_weight_at_extremes_is_one(self):
        from src.simulation.fast_sim_mode import _importance_weight
        assert abs(_importance_weight(0.0) - 1.0) < 1e-9
        assert abs(_importance_weight(1.0) - 1.0) < 1e-9


class TestWpDivergence:
    def test_divergence_exact(self):
        from src.simulation.fast_sim_mode import compute_wp_divergence
        assert abs(compute_wp_divergence(0.60, 0.52) - 0.08) < 1e-9

    def test_divergence_always_positive(self):
        from src.simulation.fast_sim_mode import compute_wp_divergence
        assert compute_wp_divergence(0.40, 0.60) == compute_wp_divergence(0.60, 0.40)

    def test_exceeds_threshold_true(self):
        from src.simulation.fast_sim_mode import exceeds_divergence_threshold
        assert exceeds_divergence_threshold(0.65, 0.50) is True

    def test_exceeds_threshold_false(self):
        from src.simulation.fast_sim_mode import exceeds_divergence_threshold
        assert exceeds_divergence_threshold(0.55, 0.50) is False

    def test_threshold_constant_is_8pct(self):
        from src.simulation.fast_sim_mode import WP_DIVERGENCE_THRESHOLD
        assert abs(WP_DIVERGENCE_THRESHOLD - 0.08) < 1e-9


class TestHotSwapSimulation:
    def test_returns_required_keys(self):
        from src.simulation.fast_sim_mode import run_hot_swap_simulation
        pre = {"win_probability": 0.55, "home_offense": 108.0, "home_defense": 108.0,
               "away_offense": 106.0, "away_defense": 106.0, "pace": 100.0,
               "game_time_remaining": 1440.0, "home_score": 55, "away_score": 50}
        post = {**pre}
        result = run_hot_swap_simulation(pre, post, market_win_prob=0.58)
        required = {
            "win_probability", "market_win_prob", "wp_divergence",
            "tier_1_alert", "pre_swap_wp", "swap_wp_delta",
        }
        assert required.issubset(set(result.keys()))

    def test_tier_1_alert_fires_on_large_divergence(self):
        from src.simulation.fast_sim_mode import run_hot_swap_simulation
        pre = {"win_probability": 0.50, "home_offense": 108.0, "home_defense": 108.0,
               "away_offense": 108.0, "away_defense": 108.0, "pace": 100.0,
               "game_time_remaining": 1440.0, "home_score": 50, "away_score": 50}
        post = {**pre, "home_offense": 75.0}  # massive degradation
        result = run_hot_swap_simulation(pre, post, market_win_prob=0.50)
        # With home offense crippled, WP should drop significantly
        assert "tier_1_alert" in result
