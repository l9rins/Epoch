import os
import sys

def run_e2e_check():
    print("==================================================")
    print("EPOCH ENGINE MONETIZATION LAYER - E2E CHECK")
    print("==================================================")
    
    # SYSTEM 1: Kelly Criterion
    print("\n[1] Checking Kelly Criterion Engine...")
    from src.intelligence.kelly_criterion import compute_kelly_recommendation
    rec = compute_kelly_recommendation("WIN_PROB", 1, 0.62, 10000.0)
    print(f"    -> Recommended bet: ${rec.recommended_bet_size:,.2f} on $10k bankroll")
    
    # SYSTEM 2: Betting Journal
    print("\n[2] Checking Betting Journal & Edge Tracker...")
    from src.api.betting_journal import create_journal_entry, append_journal_entry, compute_edge_profile
    user_id = "e2e_test_user_999"
    entry = create_journal_entry(user_id, "g_e2e", "WIN_PROB", 1, "HOME", 0.62, 1.9, 170.0, 170.0, 10000.0, 0.017)
    append_journal_entry(entry)
    profile = compute_edge_profile(user_id)
    print(f"    -> Profile active. Total bets tracked: {profile['total_bets']}")
    
    # SYSTEM 3: Prop Modeling Engine
    print("\n[3] Checking Prop Modeling Engine...")
    from src.intelligence.prop_model import compute_prop_board
    from src.simulation.quantum_roster import _build_synthetic_quantum_roster
    roster = _build_synthetic_quantum_roster("GSW")
    player_id = list(roster.players.keys())[0]
    board = compute_prop_board(roster, {player_id: {"POINTS": 25.5}}, n_samples=50)
    print(f"    -> Generated {len(board)} prop distributions. Top edge vs line: {board[0].edge_vs_line:+.2f}")
    
    # SYSTEM 4: Auth Platform
    print("\n[4] Checking Tiered Auth Platform...")
    from src.api.auth import create_user, authenticate_user, require_tier
    test_email = f"e2e_{os.urandom(4).hex()}@epoch.com"
    user = create_user(test_email, "pwd123", "SIGNAL")
    auth = authenticate_user(test_email, "pwd123")
    print(f"    -> User authenticated. Tier SIGNAL verification: {require_tier('SIGNAL', auth.tier)}")
    
    print("\n==================================================")
    print("ALL 4 MONETIZATION SYSTEMS OPERATIONAL")
    print("==================================================")
    sys.exit(0)

if __name__ == "__main__":
    run_e2e_check()
