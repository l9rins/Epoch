import json
import numpy as np
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from collections import defaultdict

from src.simulation.quantum_roster import (
    PlayerPerformanceDistribution,
    QuantumRoster,
    ARCHETYPE_DISTRIBUTIONS,
    NIGHT_TYPE_PROBS,
)

MIN_PLAYER_GAMES = 20
PLAYER_DISTRIBUTIONS_PATH = Path("data/player_distributions.json")

# Stat field mapping from player log to attribute space
STAT_TO_ATTRIBUTE = {
    "points":   "scoring",
    "assists":  "playmaking",
    "rebounds": "strength",
    "threes_made": "shooting",
    "steals":   "athleticism",
    "blocks":   "athleticism",
}

@dataclass
class LearnedPlayerDistribution:
    player_id: str
    player_name: str
    team: str
    season: str
    game_count: int
    night_type_probs: Dict[str, float]
    attribute_means: Dict[str, float]
    attribute_stds: Dict[str, float]
    per_stat_means: Dict[str, float]
    per_stat_stds: Dict[str, float]
    archetype: str
    data_source: str  # "real" or "archetype_default"

    def to_quantum_distribution(self) -> PlayerPerformanceDistribution:
        """Convert learned distribution to QuantumRoster-compatible format."""
        return PlayerPerformanceDistribution(
            player_id=self.player_id,
            player_name=self.player_name,
            archetype=self.archetype,
            base_attributes=self.attribute_means,
            variance_by_field=self.attribute_stds,
        )

def _classify_archetype(
    per_stat_means: Dict[str, float],
) -> str:
    """Classify a player's archetype from their stat averages."""
    pts = per_stat_means.get("points", 10.0)
    ast = per_stat_means.get("assists", 3.0)
    reb = per_stat_means.get("rebounds", 4.0)
    fg3 = per_stat_means.get("threes_made", 1.5)
    stl = per_stat_means.get("steals", 1.0)

    if pts > 22 and ast > 6:
        return "playmaker"
    elif pts > 22 and fg3 > 3:
        return "elite_scorer"
    elif pts > 22:
        return "elite_scorer"
    elif fg3 > 2.5:
        return "3pt_specialist"
    elif reb > 8 and stl < 1.5:
        return "defensive_anchor"
    else:
        return "role_player"

def _normalize_stats_to_attributes(
    per_stat_means: Dict[str, float],
    per_stat_stds: Dict[str, float],
) -> Tuple[Dict[str, float], Dict[str, float]]:
    """
    Convert real stat means/stds to normalized 0-1 attribute space.
    Normalization targets based on elite player benchmarks.
    """
    STAT_ELITE_BENCHMARKS = {
        "points":     35.0,
        "assists":    12.0,
        "rebounds":   14.0,
        "threes_made": 6.0,
        "steals":      3.5,
        "blocks":      3.5,
    }

    means = {}
    stds = {}

    for stat, attr in STAT_TO_ATTRIBUTE.items():
        benchmark = STAT_ELITE_BENCHMARKS.get(stat, 10.0)
        mean_val = per_stat_means.get(stat, 0.0)
        std_val = per_stat_stds.get(stat, mean_val * 0.3)

        normalized_mean = min(1.0, mean_val / benchmark)
        normalized_std = min(0.5, std_val / benchmark)

        # Aggregate multiple stats that map to same attribute
        if attr not in means:
            means[attr] = normalized_mean
            stds[attr] = normalized_std
        else:
            # Average if multiple stats map to same attribute
            means[attr] = (means[attr] + normalized_mean) / 2.0
            stds[attr] = max(stds[attr], normalized_std)

    # Ensure all required attributes have values
    for attr in ["scoring", "playmaking", "strength", "shooting", "athleticism", "defense"]:
        if attr not in means:
            means[attr] = 0.5
            stds[attr] = 0.10

    return means, stds

def learn_player_distribution(
    player_id: str,
    player_logs: List[dict],
) -> LearnedPlayerDistribution:
    """
    Learn performance distribution for one player from their game logs.
    Falls back to archetype default if fewer than MIN_PLAYER_GAMES.
    """
    if not player_logs:
        return _default_distribution(player_id, "unknown", "UNK", "2024-25")

    player_name = player_logs[0].get("player_name", "Unknown")
    team = player_logs[0].get("team", "UNK")
    season = player_logs[0].get("season", "2024-25")

    if len(player_logs) < MIN_PLAYER_GAMES:
        dist = _default_distribution(player_id, player_name, team, season)
        dist.game_count = len(player_logs)
        return dist

    # Count night types from labeled logs
    night_type_counts = defaultdict(int)
    for log in player_logs:
        nt = log.get("night_type", "average")
        if nt in NIGHT_TYPE_PROBS:
            night_type_counts[nt] += 1

    total_labeled = sum(night_type_counts.values())
    if total_labeled > 0:
        night_type_probs = {
            nt: round(night_type_counts[nt] / total_labeled, 4)
            for nt in NIGHT_TYPE_PROBS.keys()
        }
        # Fill missing types with small prior
        for nt in NIGHT_TYPE_PROBS:
            if nt not in night_type_probs:
                night_type_probs[nt] = 0.02
        # Renormalize
        total = sum(night_type_probs.values())
        night_type_probs = {k: round(v / total, 4) for k, v in night_type_probs.items()}
    else:
        night_type_probs = dict(NIGHT_TYPE_PROBS)

    # Compute per-stat means and stds
    per_stat_means = {}
    per_stat_stds = {}
    for stat in ["points", "assists", "rebounds", "threes_made", "steals", "blocks"]:
        values = [log.get(stat, 0.0) for log in player_logs if log.get("minutes", 0) > 10]
        if values:
            per_stat_means[stat] = round(float(np.mean(values)), 2)
            per_stat_stds[stat] = round(float(np.std(values)), 2)
        else:
            per_stat_means[stat] = 0.0
            per_stat_stds[stat] = 0.0

    attribute_means, attribute_stds = _normalize_stats_to_attributes(
        per_stat_means, per_stat_stds
    )
    archetype = _classify_archetype(per_stat_means)

    return LearnedPlayerDistribution(
        player_id=player_id,
        player_name=player_name,
        team=team,
        season=season,
        game_count=len(player_logs),
        night_type_probs=night_type_probs,
        attribute_means=attribute_means,
        attribute_stds=attribute_stds,
        per_stat_means=per_stat_means,
        per_stat_stds=per_stat_stds,
        archetype=archetype,
        data_source="real",
    )

def _default_distribution(
    player_id: str,
    player_name: str,
    team: str,
    season: str,
) -> LearnedPlayerDistribution:
    """Default archetype distribution when real data is insufficient."""
    return LearnedPlayerDistribution(
        player_id=player_id,
        player_name=player_name,
        team=team,
        season=season,
        game_count=0,
        night_type_probs=dict(NIGHT_TYPE_PROBS),
        attribute_means={
            "scoring": 0.65, "playmaking": 0.55, "strength": 0.55,
            "shooting": 0.60, "athleticism": 0.65, "defense": 0.55,
        },
        attribute_stds={
            "scoring": 0.12, "playmaking": 0.10, "strength": 0.08,
            "shooting": 0.13, "athleticism": 0.08, "defense": 0.07,
        },
        per_stat_means={"points": 10.0, "assists": 2.0, "rebounds": 3.0, "threes_made": 1.0, "steals": 0.5, "blocks": 0.5},
        per_stat_stds={"points": 3.0, "assists": 1.0, "rebounds": 1.5, "threes_made": 0.5, "steals": 0.5, "blocks": 0.5},
        archetype="role_player",
        data_source="archetype_default",
    )

def learn_all_player_distributions(
    player_logs: List[dict],
) -> Dict[str, LearnedPlayerDistribution]:
    """
    Learn distributions for all players in the player log dataset.
    Returns dict of player_id → LearnedPlayerDistribution.
    """
    # Group logs by player
    player_log_groups: Dict[str, List[dict]] = defaultdict(list)
    for log in player_logs:
        player_log_groups[log["player_id"]].append(log)

    distributions = {}
    real_count = 0
    default_count = 0

    for player_id, logs in player_log_groups.items():
        dist = learn_player_distribution(player_id, logs)
        distributions[player_id] = dist
        if dist.data_source == "real":
            real_count += 1
        else:
            default_count += 1

    print(f"Learned {real_count} real distributions, {default_count} archetype defaults")

    # Save to disk
    PLAYER_DISTRIBUTIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
    serialized = {}
    for pid, dist in distributions.items():
        serialized[pid] = asdict(dist)
    with open(PLAYER_DISTRIBUTIONS_PATH, "w") as f:
        json.dump(serialized, f, indent=2)

    return distributions

def load_player_distributions() -> Dict[str, LearnedPlayerDistribution]:
    """Load learned player distributions from disk."""
    if not PLAYER_DISTRIBUTIONS_PATH.exists():
        return {}
    try:
        with open(PLAYER_DISTRIBUTIONS_PATH) as f:
            data = json.load(f)
        return {
            pid: LearnedPlayerDistribution(**entry)
            for pid, entry in data.items()
        }
    except Exception as e:
        print(f"Warning loading player distributions: {e}")
        return {}

def build_quantum_roster_from_learned_distributions(
    team: str,
    player_ids: List[str],
    distributions: Dict[str, LearnedPlayerDistribution],
) -> QuantumRoster:
    """
    Build a QuantumRoster using learned per-player distributions.
    Falls back to archetype default for players without real data.
    """
    from src.simulation.quantum_roster import QuantumRoster
    roster = QuantumRoster(team_abbr=team)
    for player_id in player_ids:
        if player_id in distributions:
            dist = distributions[player_id]
        else:
            dist = _default_distribution(player_id, player_id, team, "2024-25")
        quantum_dist = dist.to_quantum_distribution()
        roster.add_player(quantum_dist)
    return roster
