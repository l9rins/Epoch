from src.intelligence.prop_model import compute_prop_board, PropDistribution
from src.simulation.quantum_roster import _build_synthetic_quantum_roster

def test_compute_prop_board():
    roster = _build_synthetic_quantum_roster("GSW")
    
    # Curry logic expects internal ID "GSW_PG", but let's test safely
    player_id = list(roster.players.keys())[0]  
    
    lines = {
        player_id: {
            "POINTS": 22.5,
            "ASSISTS": 5.5
        }
    }
    
    board = compute_prop_board(roster, lines, causal_usage_factors={player_id: 1.15}, n_samples=100)
    
    assert len(board) == 2
    assert all(isinstance(p, PropDistribution) for p in board)
    assert any(p.prop_type == "POINTS" for p in board)
    
    points_prop = next(p for p in board if p.prop_type == "POINTS")
    assert 0.0 <= points_prop.over_probability <= 1.0
    assert 0.0 <= points_prop.under_probability <= 1.0
    assert points_prop.prop_line == 22.5
    assert points_prop.sample_count == 100
