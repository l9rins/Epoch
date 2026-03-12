import pytest
from src.simulation.player_distributions import (
    _classify_archetype,
    _normalize_stats_to_attributes,
    learn_player_distribution,
    build_quantum_roster_from_learned_distributions,
    NIGHT_TYPE_PROBS,
)

def test_classify_archetype():
    playmaker = {"points": 25.0, "assists": 8.0, "rebounds": 5.0}
    assert _classify_archetype(playmaker) == "playmaker"
    
    scorer = {"points": 28.0, "assists": 4.0, "threes_made": 3.5}
    assert _classify_archetype(scorer) == "elite_scorer"
    
    shooter = {"points": 15.0, "assists": 2.0, "threes_made": 3.2}
    assert _classify_archetype(shooter) == "3pt_specialist"
    
    anchor = {"points": 12.0, "assists": 2.0, "rebounds": 11.0, "steals": 1.0}
    assert _classify_archetype(anchor) == "defensive_anchor"
    
    role = {"points": 8.0, "assists": 1.0, "rebounds": 3.0}
    assert _classify_archetype(role) == "role_player"

def test_normalize_stats_to_attributes():
    means = {"points": 17.5, "assists": 6.0} # 50% scoring, 50% playmaking
    stds = {"points": 3.5, "assists": 1.2} # 10% std
    
    attr_means, attr_stds = _normalize_stats_to_attributes(means, stds)
    
    assert attr_means["scoring"] == 0.5
    assert attr_means["playmaking"] == 0.5
    assert attr_stds["scoring"] == 0.1
    # Check default fills
    assert attr_means["defense"] == 0.5

def test_learn_player_distribution_insufficient_data():
    dist = learn_player_distribution("1", [])
    assert dist.data_source == "archetype_default"
    assert dist.archetype == "role_player"
    assert dist.game_count == 0

def test_learn_player_distribution_synthetic():
    logs = [
        {"player_id": "1", "player_name": "Tatum", "team": "BOS", "season": "24",
         "minutes": 35, "points": 27, "assists": 5, "rebounds": 8, "night_type": "hot"}
    ] * 25 # 25 hot nights
    
    dist = learn_player_distribution("1", logs)
    assert dist.data_source == "real"
    assert dist.archetype == "elite_scorer"
    assert dist.game_count == 25
    assert dist.night_type_probs["hot"] > 0.8 # Dominated by hot nights

def test_build_quantum_roster():
    dist = learn_player_distribution("1", [])
    roster = build_quantum_roster_from_learned_distributions("BOS", ["1", "2"], {"1": dist})
    assert len(roster.players) == 2
    assert "1" in roster.players
    assert "2" in roster.players # Fallback created
