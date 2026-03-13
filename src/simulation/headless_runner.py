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
import asyncio
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
from src.simulation.state_logger import StateLogger
from src.intelligence.win_probability import WinProbabilityModel
from src.intelligence.momentum import MomentumTracker
from src.intelligence.signal_alerts import AlertEngine
from src.ml.calibration import CalibrationEngine
from src.api.websocket import manager as ws_manager

# NBA 2K14 team selection order (alphabetical scroll order in game)
TEAM_SELECT_ORDER = [
    "ATL", "BOS", "BKN", "CHA", "CHI", "CLE", "DAL", "DEN",
    "DET", "GSW", "HOU", "IND", "LAC", "LAL", "MEM", "MIA",
    "MIL", "MIN", "NOP", "NYK", "OKC", "ORL", "PHI", "PHX",
    "POR", "SAC", "SAS", "TOR", "UTA", "WAS"
]

TEAM_ALIASES = {
    "WARRIORS": "GSW", "LAKERS": "LAL", "CELTICS": "BOS",
    "NETS": "BKN", "KNICKS": "NYK", "BULLS": "CHI",
    "HEAT": "MIA", "SPURS": "SAS", "CLIPPERS": "LAC",
    "NUGGETS": "DEN", "SUNS": "PHX", "BUCKS": "MIL",
    "76ERS": "PHI", "SIXERS": "PHI", "RAPTORS": "TOR",
    "JAZZ": "UTA", "THUNDER": "OKC", "BLAZERS": "POR",
    "TRAILBLAZERS": "POR", "ROCKETS": "HOU", "MAVS": "DAL",
    "MAVERICKS": "DAL", "GRIZZLIES": "MEM", "WOLVES": "MIN",
    "TIMBERWOLVES": "MIN", "PACERS": "IND", "PISTONS": "DET",
    "CAVS": "CLE", "CAVALIERS": "CLE", "HAWKS": "ATL",
    "MAGIC": "ORL", "HORNETS": "CHA", "PELICANS": "NOP",
    "KINGS": "SAC", "WIZARDS": "WAS",
}

DEFAULT_TEAM_INDEX = 0  # ATL is index 0, the default starting position

class NBA2K14Automator:
    def __init__(self, pid):
        self.pid = pid
        self.app = Application(backend="win32").connect(process=pid)
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

    def _resolve_team(self, team_str: str) -> str:
        """Normalize team string to 3-letter abbreviation."""
        t = team_str.upper().strip()
        if t in TEAM_SELECT_ORDER:
            return t
        return TEAM_ALIASES.get(t, "GSW")  # fallback to GSW

    def _navigate_to_team(self, target_abbr: str, current_index: int) -> int:
        """
        Navigate team carousel from current_index to target team.
        Returns the new current_index after navigation.
        Uses shortest path (forward only for simplicity — max 30 presses).
        """
        target_index = TEAM_SELECT_ORDER.index(target_abbr)
        steps = (target_index - current_index) % len(TEAM_SELECT_ORDER)
        
        if steps == 0:
            return current_index
            
        print(f"  Navigating to {target_abbr} ({steps} presses)...")
        for _ in range(steps):
            self.send(']', delay=0.35)
        
        return target_index

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

    def start_quick_game(self, home_team: str = "GSW", away_team: str = "LAL"):
        """
        Start a quick game navigating to the correct teams dynamically.
        home_team and away_team accept full names or 3-letter abbreviations.
        """
        home_abbr = self._resolve_team(home_team)
        away_abbr = self._resolve_team(away_team)
        print(f"Starting Quick Game: {away_abbr} @ {home_abbr}")

        # Enter team select screen
        self.send(' ', delay=0.67)

        # Navigate HOME team from default position (ATL = 0)
        self._navigate_to_team(home_abbr, DEFAULT_TEAM_INDEX)
        time.sleep(0.5)

        # Switch to AWAY team selector
        self.send('a', delay=1.11)
        self.send('a', delay=0.42)

        # Navigate AWAY team from default position (ATL = 0)
        self._navigate_to_team(away_abbr, DEFAULT_TEAM_INDEX)
        time.sleep(0.5)

        # Set CPU vs CPU and start
        self.send('d', delay=2.01)
        self.send('{ENTER}', delay=0.71)

        print(f"Game started: {away_abbr} @ {home_abbr}. Handing off to monitor...")

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

async def monitor_game(reader, game_id, log_dir, win_model=None, cal_engine=None):
    """Monitor a running game until it ends, logging enriched state every tick."""
    print(f"Monitoring game {game_id}")
    
    logger = StateLogger(log_dir=str(log_dir))
    momentum_tracker = MomentumTracker()
    alert_engine = AlertEngine(log_dir=str(log_dir))
    states = []
    last_state = None
    stable_end_count = 0
    
    # One calibration sample per quarter to avoid over-weighting
    calibration_samples = {1: False, 2: False, 3: False, 4: False}

    while True:
        state = reader.read_state()
        if not state:
            print("Lost connection to game memory.")
            break
        
        # Compute analytics
        momentum = momentum_tracker(state)
        win_prob = win_model(state, momentum) if win_model else None
        proj_home, proj_away = win_model.projected_score(state) if win_model else (None, None)
        time_elapsed = win_model.calculate_time_elapsed(state) if win_model else None
        
        home_rate = (state.home_score / time_elapsed * 60) if time_elapsed and time_elapsed > 0 else 0.0
        away_rate = (state.away_score / time_elapsed * 60) if time_elapsed and time_elapsed > 0 else 0.0
        
        # Log enriched state locally
        logger.log_enriched(
            state,
            win_probability=win_prob,
            momentum=momentum,
            projected_home=proj_home,
            projected_away=proj_away,
            home_scoring_rate=home_rate,
            away_scoring_rate=away_rate,
            game_time_elapsed=time_elapsed,
        )
        states.append(state)

        # Broadcast live enriched state to WebSocket
        state_payload = {
            "type": "STATE",
            "game_id": game_id,
            "timestamp": state.timestamp,
            "quarter": state.quarter,
            "clock": round(state.clock, 2),
            "home_score": state.home_score,
            "away_score": state.away_score,
            "possession": state.possession,
            "win_probability": round(win_prob, 4) if win_prob is not None else None,
            "momentum": round(momentum, 2) if momentum is not None else None,
            "projected_home": proj_home,
            "projected_away": proj_away,
            "home_scoring_rate": round(home_rate, 2),
            "away_scoring_rate": round(away_rate, 2),
            "score_differential": state.home_score - state.away_score,
        }
        await ws_manager.broadcast(game_id, state_payload)
        
        # Process Signal Alerts
        if time_elapsed is not None and win_prob is not None and proj_home is not None:
            alerts = alert_engine.process(
                game_time=time_elapsed,
                win_prob=win_prob,
                momentum=momentum,
                proj_home=proj_home,
                proj_away=proj_away
            )
            for alert in alerts:
                alert_payload = {
                    "type": "ALERT",
                    "game_id": game_id,
                    "alert_type": alert.alert_type,
                    "tier": alert.tier,
                    "value": alert.value,
                    "message": alert.message,
                    "timestamp": alert.timestamp,
                }
                await ws_manager.broadcast(game_id, alert_payload)

        # Record prediction for calibration
        if win_prob is not None and cal_engine and state.quarter in calibration_samples:
            if not calibration_samples[state.quarter] and state.clock <= 30:
                calibration_samples[state.quarter] = win_prob
        
        # Display progress
        if len(states) % 20 == 0:
            wp_str = f" WP:{win_prob:.1%}" if win_prob is not None else ""
            print(f"  Q{state.quarter} {state.clock:.1f}s | {state.home_score}-{state.away_score}{wp_str}")

        # Detect game end: Q4, clock 0, stable for 10 seconds
        if state.quarter >= 4 and state.clock <= 0:
            if last_state and state.home_score == last_state.home_score and \
               state.away_score == last_state.away_score:
                stable_end_count += 1
            else:
                stable_end_count = 0
            
            if stable_end_count >= 20:
                print("Game end detected (stable final score).")
                break
        
        last_state = state
        await asyncio.sleep(0.5)

    if not states:
        return None
        
    final = states[-1]
    home_won = final.home_score > final.away_score
    
    # Finalize calibration samples
    if cal_engine:
        for q, pred in calibration_samples.items():
            if isinstance(pred, float):
                cal_engine.log_outcome(pred, home_won)

    result = logger.summary()
    result["game_id"] = game_id
    return result

async def run_batch(num_games, home_team, away_team):
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

    for i in range(num_games):
        game_id = str(uuid.uuid4())[:8]
        print(f"\n=== GAME {i+1}/{num_games} (ID: {game_id}) ===")
        
        # Check if game is already running
        s = reader.read_state()
        if s and s.quarter > 0:
            print("Game already in progress. Skipping automation...")
        else:
            automator.start_quick_game(home_team, away_team)
        
        # Wait for tipoff (Quarter becomes 1)
        print("Waiting for tipoff...")
        start_wait = time.time()
        while time.time() - start_wait < 60:
            s = reader.read_state()
            if s and s.quarter > 0:
                break
            await asyncio.sleep(1)

        result = await monitor_game(reader, game_id, log_dir, win_model, cal_engine)
        
        # STEP 7 / Exit sequence
        automator.exit_to_main_menu()

        if result:
            result["timestamp"] = time.time()
            result["home_team"] = home_team
            result["away_team"] = away_team
            
            with open(results_file, "a") as f:
                f.write(json.dumps(result) + "\n")
            print(f"Game Recorded: {result['home_score']}-{result['away_score']} ({result['winner']})")
        
        await asyncio.sleep(5)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--games", type=int, default=1)
    parser.add_argument("--home", default="warriors")
    parser.add_argument("--away", default="lakers")
    args = parser.parse_args()

    asyncio.run(run_batch(args.games, args.home, args.away))
