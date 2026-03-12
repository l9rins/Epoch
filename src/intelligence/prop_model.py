import numpy as np
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from enum import Enum

from src.simulation.quantum_roster import (
    PlayerPerformanceDistribution,
    QuantumRoster,
    _build_synthetic_quantum_roster,
    ARCHETYPE_DISTRIBUTIONS,
)

class PropType(str, Enum):
    POINTS = "POINTS"
    ASSISTS = "ASSISTS"
    REBOUNDS = "REBOUNDS"
    THREES_MADE = "THREES_MADE"
    POINTS_REBOUNDS_ASSISTS = "POINTS_REBOUNDS_ASSISTS"
    STEALS = "STEALS"
    BLOCKS = "BLOCKS"

# Stat scaling constants — tuned to 2024-25 NBA averages
STAT_SCALE = {
    PropType.POINTS:    35.0,
    PropType.ASSISTS:   12.0,
    PropType.REBOUNDS:  14.0,
    PropType.THREES_MADE: 6.0,
    PropType.STEALS:    3.0,
    PropType.BLOCKS:    3.0,
}

@dataclass
class PropDistribution:
    player_id: str
    player_name: str
    prop_type: PropType
    prop_line: float
    over_probability: float
    under_probability: float
    push_probability: float
    distribution: Dict[str, float]  # p10, p25, p50, p75, p90
    mean_projection: float
    std_projection: float
    causal_factors: List[str]
    sample_count: int
    edge_vs_line: float   # positive = lean over, negative = lean under
    confidence: str       # "HIGH", "MEDIUM", "LOW"

def _attributes_to_stat(
    attributes: Dict[str, float],
    prop_type: PropType,
) -> float:
    """Map normalized 0-1 player attributes to a raw stat projection."""
    scoring = attributes.get("scoring", 0.7)
    shooting = attributes.get("shooting", 0.7)
    defense = attributes.get("defense", 0.65)
    athleticism = attributes.get("athleticism", 0.7)
    playmaking = attributes.get("playmaking", 0.6)
    strength = attributes.get("strength", 0.5)

    if prop_type == PropType.POINTS:
        raw = (scoring * 0.60 + athleticism * 0.20 + playmaking * 0.20)
    elif prop_type == PropType.ASSISTS:
        raw = (playmaking * 0.70 + scoring * 0.15 + shooting * 0.15)
    elif prop_type == PropType.REBOUNDS:
        raw = (0.50 + strength * 0.30 + athleticism * 0.20)
    elif prop_type == PropType.THREES_MADE:
        raw = (shooting * 0.80 + scoring * 0.20)
    elif prop_type == PropType.STEALS:
        raw = (athleticism * 0.60 + playmaking * 0.40)
    elif prop_type == PropType.BLOCKS:
        raw = (strength * 0.50 + athleticism * 0.50)
    elif prop_type == PropType.POINTS_REBOUNDS_ASSISTS:
        pts = (scoring * 0.60 + athleticism * 0.20 + playmaking * 0.20) * STAT_SCALE[PropType.POINTS]
        reb = (0.50 + strength * 0.30 + athleticism * 0.20) * STAT_SCALE[PropType.REBOUNDS]
        ast = (playmaking * 0.70 + scoring * 0.15 + shooting * 0.15) * STAT_SCALE[PropType.ASSISTS]
        return pts + reb + ast
    else:
        raw = scoring * 0.5 + athleticism * 0.5

    return raw * STAT_SCALE.get(prop_type, 20.0)

def compute_prop_distribution(
    player_id: str,
    player_name: str,
    player_dist: PlayerPerformanceDistribution,
    prop_type: PropType,
    prop_line: float,
    n_samples: int = 1000,
    causal_injury_factor: float = 1.0,
    causal_usage_factor: float = 1.0,
    causal_factors: Optional[List[str]] = None,
    seed: Optional[int] = None,
) -> PropDistribution:
    """
    Run N quantum samples for one player and compute prop probabilities.
    causal_injury_factor: 1.0 = healthy, 0.5 = major injury impact
    causal_usage_factor: 1.0 = normal usage, 1.15 = star teammate out
    """
    rng = np.random.default_rng(seed)
    causal_factors = causal_factors or []

    stat_samples = []
    for _ in range(n_samples):
        sample = player_dist.sample(
            rng,
            fatigue_factor=1.0,
            injury_factor=causal_injury_factor,
        )
        attrs = sample["attributes"]

        # Apply causal usage adjustment to scoring/playmaking
        adjusted_attrs = attrs.copy()
        adjusted_attrs["scoring"] = min(1.0, attrs.get("scoring", 0.7) * causal_usage_factor)
        adjusted_attrs["playmaking"] = min(1.0, attrs.get("playmaking", 0.6) * causal_usage_factor)

        stat = _attributes_to_stat(adjusted_attrs, prop_type)

        # Add game-level noise
        noise_std = stat * 0.18  # 18% coefficient of variation
        stat_with_noise = max(0.0, stat + rng.normal(0, noise_std))
        stat_samples.append(stat_with_noise)

    samples = np.array(stat_samples)
    mean_proj = float(np.mean(samples))
    std_proj = float(np.std(samples))

    # Compute over/under probabilities
    # Use 0.5 as push threshold window
    push_window = max(0.5, prop_line * 0.02)
    over_count = np.sum(samples > prop_line + push_window)
    under_count = np.sum(samples < prop_line - push_window)
    push_count = n_samples - over_count - under_count

    over_prob = float(over_count / n_samples)
    under_prob = float(under_count / n_samples)
    push_prob = float(push_count / n_samples)

    percentiles = np.percentile(samples, [10, 25, 50, 75, 90])
    distribution = {
        "p10": round(float(percentiles[0]), 1),
        "p25": round(float(percentiles[1]), 1),
        "p50": round(float(percentiles[2]), 1),
        "p75": round(float(percentiles[3]), 1),
        "p90": round(float(percentiles[4]), 1),
    }

    # Edge vs line: positive = lean over
    edge_vs_line = (mean_proj - prop_line) / max(std_proj, 1.0)

    confidence = (
        "HIGH" if abs(over_prob - 0.5) > 0.10
        else "MEDIUM" if abs(over_prob - 0.5) > 0.05
        else "LOW"
    )

    return PropDistribution(
        player_id=player_id,
        player_name=player_name,
        prop_type=prop_type,
        prop_line=prop_line,
        over_probability=round(over_prob, 4),
        under_probability=round(under_prob, 4),
        push_probability=round(push_prob, 4),
        distribution=distribution,
        mean_projection=round(mean_proj, 2),
        std_projection=round(std_proj, 2),
        causal_factors=causal_factors,
        sample_count=n_samples,
        edge_vs_line=round(edge_vs_line, 4),
        confidence=confidence,
    )

def compute_prop_board(
    roster: QuantumRoster,
    prop_lines: Dict[str, Dict[str, float]],
    causal_injury_factors: Optional[Dict[str, float]] = None,
    causal_usage_factors: Optional[Dict[str, float]] = None,
    n_samples: int = 1000,
) -> List[PropDistribution]:
    """
    Compute prop distributions for all players on a roster.
    prop_lines: {player_id: {prop_type: line_value}}
    Returns sorted by edge magnitude (highest conviction first).
    """
    causal_injury_factors = causal_injury_factors or {}
    causal_usage_factors = causal_usage_factors or {}
    results = []

    for player_id, player_dist in roster.players.items():
        player_props = prop_lines.get(player_id, {})
        for prop_type_str, line in player_props.items():
            try:
                prop_type = PropType(prop_type_str)
            except ValueError:
                continue

            injury_factor = causal_injury_factors.get(player_id, 1.0)
            usage_factor = causal_usage_factors.get(player_id, 1.0)

            dist = compute_prop_distribution(
                player_id=player_id,
                player_name=player_dist.player_name,
                player_dist=player_dist,
                prop_type=prop_type,
                prop_line=line,
                n_samples=n_samples,
                causal_injury_factor=injury_factor,
                causal_usage_factor=usage_factor,
            )
            results.append(dist)

    # Sort by conviction (distance from 50/50)
    results.sort(key=lambda x: abs(x.over_probability - 0.5), reverse=True)
    return results
