import os
from src.api.betting_journal import (
    create_journal_entry,
    append_journal_entry,
    resolve_outcome,
    load_user_journal,
    compute_edge_profile,
    JOURNAL_PATH,
)

def test_journal_flow():
    test_user = "test_user_journal_123"
    
    # Ensure fresh state for test user
    if JOURNAL_PATH.exists():
        lines = []
        with open(JOURNAL_PATH, "r") as f:
            for line in f:
                if test_user not in line:
                    lines.append(line)
        with open(JOURNAL_PATH, "w") as f:
            f.writelines(lines)
            
    # Create entries
    e1 = create_journal_entry(test_user, "g1", "WIN_PROB", 1, "HOME", 0.60, 1.9, 100.0, 100.0, 10000.0, 0.01)
    e2 = create_journal_entry(test_user, "g2", "WIN_PROB", 2, "AWAY", 0.55, 1.9, 50.0, 50.0, 10000.0, 0.005)
    
    append_journal_entry(e1)
    append_journal_entry(e2)
    
    entries = load_user_journal(test_user)
    assert len(entries) == 2
    
    # Resolve outcomes
    assert resolve_outcome(e1.journal_id, "WIN", +90.0) == True
    assert resolve_outcome(e2.journal_id, "LOSS", -50.0) == True
    
    entries = load_user_journal(test_user)
    assert entries[0]["outcome"] == "WIN"
    assert entries[1]["outcome"] == "LOSS"
    
def test_edge_profile_computation():
    test_user = "test_edge_user_456"
    
    # Need 30+ samples to hit MIN_SAMPLES_FOR_EDGE_PROFILE
    for i in range(35):
        e = create_journal_entry(test_user, f"g{i}", "TEST_SIG", 1, "H", 0.6, 1.9, 100.0, 100.0, 10000.0, 0.01)
        append_journal_entry(e)
        outcome = "WIN" if i % 2 == 0 else "LOSS"
        profit = 90.0 if outcome == "WIN" else -100.0
        resolve_outcome(e.journal_id, outcome, profit)
        
    profile = compute_edge_profile(test_user)
    assert profile["total_bets"] == 35
    assert profile["profile_confidence"] == "MEDIUM"
    assert "TEST_SIG" in profile["signal_type_edges"]
    assert "TEST_SIG" in profile["kelly_multipliers"]
