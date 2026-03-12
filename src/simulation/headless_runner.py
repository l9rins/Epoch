"""
Headless Batch Simulator (System A)
Automates NBA 2K14 using pywinauto for menu navigation and 
MemoryReader for game monitoring.

Requirements:
- nba2k14.exe must be running or reachable.
- pywinauto installed.
"""

import os
import sys
import time
import json
import uuid
import argparse
from pathlib import Path
from dataclasses import asdict

# Import pywinauto
try:
    from pywinauto import Application
    from pywinauto.keyboard import send_keys
except ImportError:
    print("Error: pywinauto not installed. Run 'pip install pywinauto'")
    sys.exit(1)

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.simulation.process_manager import get_nba2k14_pid, wait_for_process
from src.simulation.memory_reader import MemoryReader
from src.intelligence.win_probability import WinProbabilityModel
from src.ml.calibration import CalibrationEngine

class NBA2K14Automator:
    def __init__(self, pid):
        self.pid = pid
        self.app = Application().connect(process=pid)
        self.window = self.app.top_window()
        print(f"Connected to NBA 2K14 (PID: {pid})")

    def focus(self):
        """Bring game window to foreground."""
        try:
            self.window.set_focus()
            time.sleep(0.5)
        except Exception as e:
            print(f"Warning: Could not focus window: {e}")

    def send(self, keys, delay=1.0):
        """Send key sequence with delay."""
        self.focus()
        print(f"  Sending: {keys}")
        send_keys(keys)
        time.sleep(delay)

    def navigate_to_main_menu(self):
        """Minimal menu clearing to avoid breaking state."""
        print("Ensuring Main Menu state...")
        # Just a single Esc to clear any accidental overlays, but avoid 'Quit Game' prompts
        self.send("{VK_ESCAPE}", delay=1.0)

    def set_one_minute_quarters(self):
        """Navigate to settings and set 1-minute quarters."""
        print("Setting 1-minute quarters...")
        # Start from Main Menu
        # This path depends on the user's menu state, 
        # but usually: Options -> Game Settings -> Gameplay
        # For minimal version, we assume we are at the main menu.
        # Sequence: Right (to Options) -> Enter -> Enter (Game Settings) -> Enter (Gameplay)
        self.send("{RIGHT}" * 5, delay=0.5) # Navigate to Options tab
        self.send("{ENTER}") # Enter Options
        self.send("{ENTER}") # Enter Game Settings
        self.send("{ENTER}") # Enter Gameplay Settings
        
        # Quarter Length is usually the second or third item
        self.send("{DOWN}") 
        # Default is 12 or 5. We'll spam LEFT to reach 1 minute.
        self.send("{LEFT}" * 15, delay=0.2) 
        self.send("{ENTER}") # Confirm
        self.send("{VK_ESCAPE}" * 3) # Back to Main Menu

    def start_quick_game(self, home_team=None, away_team=None):
        """Start a quick game using the exact user-provided sequence."""
        print(f"Starting Quick Game sequence (Recorded Timing)...")
        
        self.send(' ', delay=0.67)   # enter team select
        self.send(']', delay=1.22)   # home team scroll 1
        self.send(']', delay=0.48)   # home team scroll 2
        self.send(']', delay=0.56)   # home team scroll 3
        self.send(']', delay=0.51)   # home team scroll 4 → Lakers
        self.send('a', delay=1.11)   # switch to away 1
        self.send('a', delay=0.42)   # switch to away 2
        self.send(']', delay=0.70)   # away team scroll 1
        self.send(']', delay=0.47)   # away team scroll 2
        self.send(']', delay=0.49)   # away team scroll 3
        self.send(']', delay=0.56)   # away team scroll 4
        self.send(']', delay=2.24)   # away team scroll 5 → Warriors
        self.send('d', delay=2.01)   # CPU vs CPU
        self.send('{ENTER}', delay=0.71)  # start game
        
        print("Game started. Handing off to monitor...")

    def exit_to_main_menu(self):
        """Exit to main menu after game completion using precise sequence."""
        print("Exiting to Main Menu...")
        time.sleep(3) # Wait for final screens
        
        self.send('d', delay=0.5)   # × 5 to reach Quit
        self.send('d', delay=0.5)
        self.send('d', delay=0.5)
        self.send('d', delay=0.5)
        self.send('d', delay=0.5)
        self.send('{ENTER}', delay=3.0)  # confirm quit
        
        print("Returned to Main Menu.")

def monitor_game(reader, game_id, log_dir, win_model=None, cal_engine=None):
    """Monitor a running game until it ends."""
    log_file = log_dir / f"game_{game_id}.jsonl"
    print(f"Monitoring game {game_id}, logging to {log_file}")
    
    states = []
    last_state = None
    stable_end_count = 0
    
    # We'll take a few sample predictions for the calibration engine
    # e.g., one per quarter to avoid over-weighting a single game
    calibration_samples = {1: False, 2: False, 3: False, 4: False}

    with open(log_file, "w") as f:
        while True:
            state = reader.read_state()
            if not state:
                print("Lost connection to game memory.")
                break
            
            # Log state
            state_dict = {
                "timestamp": state.timestamp,
                "quarter": state.quarter,
                "clock": state.clock,
                "home_score": state.home_score,
                "away_score": state.away_score,
                "possession": state.possession
            }
            f.write(json.dumps(state_dict) + "\n")
            states.append(state)
            
            # Record prediction for calibration
            if win_model and cal_engine and state.quarter in calibration_samples:
                # Take sample at the middle of the quarter (~6min/2 or 1min/2)
                if not calibration_samples[state.quarter] and state.clock <= 30:
                    prob = win_model(state)
                    # We store the prediction now, and will resolve it with the outcome later
                    calibration_samples[state.quarter] = prob
            
            # Display progress
            if len(states) % 20 == 0:
                print(f"  Q{state.quarter} {state.clock:.1f}s | {state.home_score}-{state.away_score}")

            # Detect game end: Q4, clock 0, and no changes for 10 seconds
            if state.quarter >= 4 and state.clock <= 0:
                if last_state and state.home_score == last_state.home_score and \
                   state.away_score == last_state.away_score:
                    stable_end_count += 1
                else:
                    stable_end_count = 0
                
                # Check every 0.5s, so 20 stable polls = 10s
                if stable_end_count >= 20:
                    print("Game end detected (stable final score).")
                    break
            
            last_state = state
            time.sleep(0.5)

    if not states:
        return None
        
    final = states[-1]
    home_won = final.home_score > final.away_score
    winner = "HOME" if home_won else "AWAY"
    if final.home_score == final.away_score: winner = "TIE"
    
    # Finalize calibration samples
    if cal_engine:
        for q, pred in calibration_samples.items():
            if isinstance(pred, float):
                cal_engine.log_outcome(pred, home_won)

    return {
        "game_id": game_id,
        "home_score": final.home_score,
        "away_score": final.away_score,
        "winner": winner,
        "duration_states": len(states)
    }

def run_batch(num_games, home_team, away_team):
    log_dir = Path("data/batch_logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    results_file = Path("data/batch_results.jsonl")

    pid = wait_for_process(timeout=30)
    if not pid:
        print("Error: NBA 2K14 not found.")
        return

    automator = NBA2K14Automator(pid)
    reader = MemoryReader(pid)
    win_model = WinProbabilityModel()
    cal_engine = CalibrationEngine()

    # Initial Setup (Skipped as requested for manual main menu start)
    # automator.navigate_to_main_menu()
    # automator.set_one_minute_quarters()

    for i in range(num_games):
        game_id = str(uuid.uuid4())[:8]
        print(f"\n=== GAME {i+1}/{num_games} (ID: {game_id}) ===")
        
        # We start directly at Main Menu or rely on exit_to_main_menu from previous game
        # automator.navigate_to_main_menu()
        automator.start_quick_game(home_team, away_team)
        
        # Wait for tipoff (Quarter becomes 1)
        print("Waiting for tipoff...")
        start_wait = time.time()
        while time.time() - start_wait < 60:
            s = reader.read_state()
            if s and s.quarter > 0:
                break
            time.sleep(1)

        result = monitor_game(reader, game_id, log_dir, win_model, cal_engine)
        
        # STEP 7 / Exit sequence
        automator.exit_to_main_menu()

        if result:
            result["timestamp"] = time.time()
            result["home_team"] = home_team
            result["away_team"] = away_team
            
            with open(results_file, "a") as f:
                f.write(json.dumps(result) + "\n")
            print(f"Game Recorded: {result['home_score']}-{result['away_score']} ({result['winner']})")
        
        # Small wait before next iteration
        time.sleep(5)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--games", type=int, default=1)
    parser.add_argument("--home", default="warriors")
    parser.add_argument("--away", default="lakers")
    args = parser.parse_args()

    run_batch(args.games, args.home, args.away)
