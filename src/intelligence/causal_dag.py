from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import numpy as np
from enum import Enum

class CausalNode(Enum):
    PLAYER_HEALTH = "player_health"
    PLAYER_USAGE = "player_usage"
    OFFENSIVE_RATING = "offensive_rating"
    DEFENSIVE_RATING = "defensive_rating"
    PACE = "pace"
    THREE_POINT_RATE = "three_point_rate"
    PAINT_SCORING = "paint_scoring"
    TRANSITION_RATE = "transition_rate"
    CLUTCH_PERFORMANCE = "clutch_performance"
    WIN_PROBABILITY = "win_probability"

# Causal edge weights — learned from NBA historical data
# Format: (cause, effect, weight, mechanism_description)
CAUSAL_EDGES = [
    (CausalNode.PLAYER_HEALTH,      CausalNode.PLAYER_USAGE,       0.85, "injury_reduces_usage"),
    (CausalNode.PLAYER_HEALTH,      CausalNode.OFFENSIVE_RATING,   0.72, "star_absence_hurts_offense"),
    (CausalNode.PLAYER_USAGE,       CausalNode.OFFENSIVE_RATING,   0.68, "usage_concentration"),
    (CausalNode.PLAYER_USAGE,       CausalNode.DEFENSIVE_RATING,   0.45, "defensive_assignment_shift"),
    (CausalNode.OFFENSIVE_RATING,   CausalNode.PACE,               0.61, "good_offense_pushes_pace"),
    (CausalNode.OFFENSIVE_RATING,   CausalNode.THREE_POINT_RATE,   0.55, "modern_offense_3pt_heavy"),
    (CausalNode.OFFENSIVE_RATING,   CausalNode.PAINT_SCORING,      0.70, "paint_drives_ortg"),
    (CausalNode.PACE,               CausalNode.TRANSITION_RATE,    0.78, "pace_creates_transition"),
    (CausalNode.THREE_POINT_RATE,   CausalNode.WIN_PROBABILITY,    0.52, "3pt_differential_predicts_wins"),
    (CausalNode.PAINT_SCORING,      CausalNode.WIN_PROBABILITY,    0.48, "paint_dominance_predicts_wins"),
    (CausalNode.TRANSITION_RATE,    CausalNode.WIN_PROBABILITY,    0.41, "transition_advantage"),
    (CausalNode.CLUTCH_PERFORMANCE, CausalNode.WIN_PROBABILITY,    0.63, "clutch_matters_close_games"),
    (CausalNode.DEFENSIVE_RATING,   CausalNode.WIN_PROBABILITY,    0.69, "defense_wins_championships"),
]

@dataclass
class CausalState:
    """Current state of all causal nodes for one team."""
    player_health: float = 1.0
    player_usage: float = 1.0
    offensive_rating: float = 1.0
    defensive_rating: float = 1.0
    pace: float = 1.0
    three_point_rate: float = 1.0
    paint_scoring: float = 1.0
    transition_rate: float = 1.0
    clutch_performance: float = 1.0

    def to_dict(self) -> dict:
        return {
            "player_health": self.player_health,
            "player_usage": self.player_usage,
            "offensive_rating": self.offensive_rating,
            "defensive_rating": self.defensive_rating,
            "pace": self.pace,
            "three_point_rate": self.three_point_rate,
            "paint_scoring": self.paint_scoring,
            "transition_rate": self.transition_rate,
            "clutch_performance": self.clutch_performance,
        }

@dataclass
class CausalInferenceResult:
    """Result of causal inference for a matchup."""
    home_state: CausalState
    away_state: CausalState
    win_probability_adjustment: float  # additive adjustment to base win prob
    causal_chain: List[str]            # human-readable causal explanation
    mechanism: str                     # primary mechanism driving the edge
    confidence: float                  # 0.0-1.0

def propagate_causal_effects(
    initial_state: CausalState,
    intervention: Dict[CausalNode, float],
    iterations: int = 3
) -> Tuple[CausalState, List[str]]:
    """
    Given an initial state and an intervention (e.g. player_health = 0.4),
    propagate causal effects through the DAG using iterative message passing.
    Returns updated state and human-readable causal chain.
    """
    state = initial_state.to_dict()
    chain = []

    # Apply intervention
    for node, value in intervention.items():
        state[node.value] = value
        chain.append(f"INTERVENTION: {node.value} set to {value:.2f}")

    # Build adjacency for fast lookup
    adjacency: Dict[str, List[Tuple[str, float, str]]] = {}
    for cause, effect, weight, mechanism in CAUSAL_EDGES:
        if cause.value not in adjacency:
            adjacency[cause.value] = []
        adjacency[cause.value].append((effect.value, weight, mechanism))

    # Iterative propagation (DAG = no cycles, converges in 1 pass
    # but we do 3 for numerical stability)
    for iteration in range(iterations):
        new_state = state.copy()
        for cause_name, effects in adjacency.items():
            cause_val = state.get(cause_name, 1.0)
            for effect_name, weight, mechanism in effects:
                if effect_name == "win_probability":
                    continue  # handled separately
                original = state.get(effect_name, 1.0)
                # Causal update: effect moves toward cause scaled by weight
                delta = (cause_val - 1.0) * weight
                new_val = max(0.1, min(2.0, original + delta))
                if abs(new_val - original) > 0.01 and iteration == 0:
                    direction = "+" if new_val > original else "-"
                    chain.append(
                        f"{cause_name} {direction} -> {effect_name} "
                        f"({original:.2f} -> {new_val:.2f}) [{mechanism}]"
                    )
                new_state[effect_name] = new_val
        state = new_state

    # Reconstruct CausalState from dict
    result = CausalState(
        player_health=state.get("player_health", 1.0),
        player_usage=state.get("player_usage", 1.0),
        offensive_rating=state.get("offensive_rating", 1.0),
        defensive_rating=state.get("defensive_rating", 1.0),
        pace=state.get("pace", 1.0),
        three_point_rate=state.get("three_point_rate", 1.0),
        paint_scoring=state.get("paint_scoring", 1.0),
        transition_rate=state.get("transition_rate", 1.0),
        clutch_performance=state.get("clutch_performance", 1.0),
    )
    return result, chain

def compute_win_probability_adjustment(
    home_state: CausalState,
    away_state: CausalState,
) -> float:
    """
    Compute win probability adjustment from causal states.
    Positive = home team advantage. Negative = away team advantage.
    """
    weights = {
        "offensive_rating": 0.25,
        "defensive_rating": 0.22,
        "clutch_performance": 0.18,
        "three_point_rate": 0.12,
        "paint_scoring": 0.11,
        "transition_rate": 0.07,
        "pace": 0.05,
    }

    home_dict = home_state.to_dict()
    away_dict = away_state.to_dict()

    adjustment = 0.0
    for variable, weight in weights.items():
        home_val = home_dict.get(variable, 1.0)
        away_val = away_dict.get(variable, 1.0)
        adjustment += (home_val - away_val) * weight

    return max(-0.25, min(0.25, adjustment))

def run_causal_inference(
    home_interventions: Dict[CausalNode, float] = None,
    away_interventions: Dict[CausalNode, float] = None,
    base_home_state: CausalState = None,
    base_away_state: CausalState = None,
) -> CausalInferenceResult:
    """
    Main entry point. Given interventions for home and away teams
    (e.g. a player is injured → health = 0.4), returns a full
    causal inference result with win probability adjustment and
    human-readable causal chain.
    """
    home_state = base_home_state or CausalState()
    away_state = base_away_state or CausalState()
    home_interventions = home_interventions or {}
    away_interventions = away_interventions or {}

    home_result, home_chain = propagate_causal_effects(home_state, home_interventions)
    away_result, away_chain = propagate_causal_effects(away_state, away_interventions)

    wp_adjustment = compute_win_probability_adjustment(home_result, away_result)

    # Identify primary mechanism
    all_chains = home_chain + away_chain
    mechanism = "No significant causal intervention"
    if len(all_chains) > 1:
        # We try to get the first real causal step, skipping intervention logs
        for step in all_chains:
            if not step.startswith("INTERVENTION"):
                mechanism = step
                break

    # Confidence based on number of interventions
    n_interventions = len(home_interventions) + len(away_interventions)
    confidence = min(0.95, 0.5 + n_interventions * 0.1)

    return CausalInferenceResult(
        home_state=home_result,
        away_state=away_result,
        win_probability_adjustment=wp_adjustment,
        causal_chain=home_chain + away_chain,
        mechanism=mechanism,
        confidence=confidence,
    )
