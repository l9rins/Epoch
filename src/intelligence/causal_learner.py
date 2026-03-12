import json
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Tuple

CAUSAL_WEIGHTS_PATH = Path("data/models/causal_weights.json")
MIN_INJURY_SAMPLES = 20  # minimum games to learn from

# Default weights (current hardcoded priors) used as fallback
DEFAULT_CAUSAL_WEIGHTS = {
    "PLAYER_HEALTH_to_PLAYER_USAGE":       0.85,
    "PLAYER_HEALTH_to_OFFENSIVE_RATING":   0.72,
    "PLAYER_USAGE_to_OFFENSIVE_RATING":    0.68,
    "PLAYER_USAGE_to_DEFENSIVE_RATING":    0.45,
    "OFFENSIVE_RATING_to_PACE":            0.61,
    "OFFENSIVE_RATING_to_THREE_POINT_RATE": 0.55,
    "OFFENSIVE_RATING_to_PAINT_SCORING":   0.70,
    "PACE_to_TRANSITION_RATE":             0.78,
    "THREE_POINT_RATE_to_WIN_PROBABILITY": 0.52,
    "PAINT_SCORING_to_WIN_PROBABILITY":    0.48,
    "TRANSITION_RATE_to_WIN_PROBABILITY":  0.41,
    "CLUTCH_PERFORMANCE_to_WIN_PROBABILITY": 0.63,
    "DEFENSIVE_RATING_to_WIN_PROBABILITY": 0.69,
}

def _linear_regression_weight(
    X: np.ndarray,
    y: np.ndarray,
) -> Tuple[float, float]:
    """
    Fit simple OLS: y = weight * X + bias.
    Returns (weight, r_squared).
    """
    if len(X) < 3:
        return 0.0, 0.0
    X_mean = np.mean(X)
    y_mean = np.mean(y)
    numerator = np.sum((X - X_mean) * (y - y_mean))
    denominator = np.sum((X - X_mean) ** 2)
    if abs(denominator) < 1e-10:
        return 0.0, 0.0
    weight = float(numerator / denominator)
    y_pred = weight * X + (y_mean - weight * X_mean)
    ss_res = np.sum((y - y_pred) ** 2)
    ss_tot = np.sum((y - y_mean) ** 2)
    r2 = float(1 - ss_res / ss_tot) if ss_tot > 1e-10 else 0.0
    return weight, max(0.0, r2)

def learn_health_to_ortg_weight(
    injury_logs: List[dict],
) -> Tuple[float, float]:
    """
    Learn PLAYER_HEALTH → OFFENSIVE_RATING weight from injury games.
    health_delta: how much below average the team performed (proxy for health)
    ortg_delta: actual change in offensive rating
    """
    health_deltas = []
    ortg_deltas = []

    for log in injury_logs:
        ortg_before = log.get("team_ortg_before", 110.0)
        ortg_after = log.get("team_ortg_after", 110.0)
        if ortg_before <= 0:
            continue
        # Health proxy: negative z-score from pipeline = health reduction
        ortg_delta = (ortg_after - ortg_before) / max(ortg_before, 1.0)
        # Health delta: how much health was reduced (1.0 = full health, 0.3 = star out)
        health_delta = log.get("player_ortg_impact", -5.0) / 20.0
        health_delta = max(-1.0, min(0.0, health_delta))  # always negative for injury

        health_deltas.append(health_delta)
        ortg_deltas.append(ortg_delta)

    if len(health_deltas) < MIN_INJURY_SAMPLES:
        return DEFAULT_CAUSAL_WEIGHTS["PLAYER_HEALTH_to_OFFENSIVE_RATING"], 0.0

    X = np.array(health_deltas)
    y = np.array(ortg_deltas)
    weight, r2 = _linear_regression_weight(X, y)

    # Clip to reasonable range [0.3, 1.0]
    learned_weight = max(0.30, min(1.00, abs(weight)))
    return learned_weight, r2

def learn_health_to_usage_weight(
    injury_logs: List[dict],
) -> Tuple[float, float]:
    """Learn PLAYER_HEALTH → PLAYER_USAGE weight."""
    health_deltas = []
    usage_deltas = []

    for log in injury_logs:
        usage_rate = log.get("player_usage_rate", 0.25)
        # When star is out, their usage redistributes (-usage to other players)
        health_delta = log.get("player_ortg_impact", -5.0) / 20.0
        health_delta = max(-1.0, min(0.0, health_delta))
        # Usage delta: proportional to star's typical usage rate
        usage_delta = -usage_rate  # all their usage disappears

        health_deltas.append(health_delta)
        usage_deltas.append(usage_delta)

    if len(health_deltas) < MIN_INJURY_SAMPLES:
        return DEFAULT_CAUSAL_WEIGHTS["PLAYER_HEALTH_to_PLAYER_USAGE"], 0.0

    X = np.array(health_deltas)
    y = np.array(usage_deltas)
    weight, r2 = _linear_regression_weight(X, y)
    learned_weight = max(0.50, min(1.00, abs(weight)))
    return learned_weight, r2

def learn_health_to_win_prob_weight(
    injury_logs: List[dict],
) -> Tuple[float, float]:
    """
    Learn the direct DEFENSIVE_RATING → WIN_PROBABILITY weight
    as a proxy via injury game outcomes.
    """
    health_deltas = []
    wp_deltas = []

    for log in injury_logs:
        wp_delta = log.get("win_probability_delta", 0.0)
        health_delta = log.get("player_ortg_impact", -5.0) / 20.0
        health_delta = max(-1.0, min(0.0, health_delta))
        health_deltas.append(health_delta)
        wp_deltas.append(wp_delta)

    if len(health_deltas) < MIN_INJURY_SAMPLES:
        return DEFAULT_CAUSAL_WEIGHTS["DEFENSIVE_RATING_to_WIN_PROBABILITY"], 0.0

    X = np.array(health_deltas)
    y = np.array(wp_deltas)
    weight, r2 = _linear_regression_weight(X, y)
    learned_weight = max(0.30, min(0.95, abs(weight)))
    return learned_weight, r2

def learn_all_causal_weights(
    injury_logs: List[dict],
    game_logs: Optional[List[dict]] = None,
) -> dict:
    """
    Learn all causal weights from real data.
    Returns dict of edge_name → learned_weight.
    Falls back to default for edges with insufficient data.
    """
    weights = DEFAULT_CAUSAL_WEIGHTS.copy()
    r2_scores = {}
    sample_counts = {}

    print(f"Learning causal weights from {len(injury_logs)} injury games...")

    # Health -> ORtg
    w, r2 = learn_health_to_ortg_weight(injury_logs)
    weights["PLAYER_HEALTH_to_OFFENSIVE_RATING"] = round(w, 4)
    r2_scores["PLAYER_HEALTH_to_OFFENSIVE_RATING"] = round(r2, 4)
    sample_counts["PLAYER_HEALTH_to_OFFENSIVE_RATING"] = len(injury_logs)
    print(f"  HEALTH->ORTG: {w:.4f} (R²={r2:.4f})")

    # Health -> Usage
    w, r2 = learn_health_to_usage_weight(injury_logs)
    weights["PLAYER_HEALTH_to_PLAYER_USAGE"] = round(w, 4)
    r2_scores["PLAYER_HEALTH_to_PLAYER_USAGE"] = round(r2, 4)
    print(f"  HEALTH->USAGE: {w:.4f} (R²={r2:.4f})")

    # Health -> WP (via defensive rating proxy)
    w, r2 = learn_health_to_win_prob_weight(injury_logs)
    weights["DEFENSIVE_RATING_to_WIN_PROBABILITY"] = round(w, 4)
    r2_scores["DEFENSIVE_RATING_to_WIN_PROBABILITY"] = round(r2, 4)
    print(f"  DRTG->WP: {w:.4f} (R²={r2:.4f})")

    # Compute average R² across learned weights
    learned_edges = [k for k, v in r2_scores.items() if v > 0]
    avg_r2 = float(np.mean(list(r2_scores.values()))) if r2_scores else 0.0

    result = {
        "weights": weights,
        "r2_scores": r2_scores,
        "sample_counts": sample_counts,
        "avg_r2": round(avg_r2, 4),
        "learned_edges": learned_edges,
        "default_edges": [k for k in weights if k not in learned_edges],
        "r2_target_met": bool(avg_r2 > 0.20),
    }

    # Save to disk
    CAUSAL_WEIGHTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CAUSAL_WEIGHTS_PATH, "w") as f:
        json.dump(result, f, indent=2)

    print(f"Causal weights saved to {CAUSAL_WEIGHTS_PATH}")
    print(f"Average R²: {avg_r2:.4f} (target > 0.20)")
    return result

def load_causal_weights() -> Dict[str, float]:
    """
    Load learned causal weights. Falls back to defaults if file missing.
    Called by causal_dag.py at runtime.
    """
    if not CAUSAL_WEIGHTS_PATH.exists():
        return DEFAULT_CAUSAL_WEIGHTS.copy()
    try:
        with open(CAUSAL_WEIGHTS_PATH) as f:
            data = json.load(f)
        return data.get("weights", DEFAULT_CAUSAL_WEIGHTS.copy())
    except Exception:
        return DEFAULT_CAUSAL_WEIGHTS.copy()
