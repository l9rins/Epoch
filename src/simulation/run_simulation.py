import argparse
import time
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.simulation.process_manager import get_nba2k14_pid, wait_for_process
from src.simulation.memory_reader import MemoryReader
from src.simulation.state_logger import StateLogger
from src.ml.aggregator import IntelligenceAggregator, asdict
import json

def format_clock(seconds: float) -> str:
    m = int(seconds) // 60
    s = int(seconds) % 60
    return f"{m:02d}:{s:02d}"

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--team", required=True, help="Team to simulate (e.g., warriors)")
    args = parser.parse_args()
    
    print(f"Loading {args.team}_poc.ros... (Phase 5 placeholder)")
    # Logic to move file into Saves directory could be added here if OS paths were known
    
    print("Waiting for nba2k14.exe...")
    pid = wait_for_process()
    if not pid:
        print("Could not find nba2k14.exe process.", file=sys.stderr)
        sys.exit(1)
        
    print(f"Found nba2k14 process: PID {pid}")
    
    try:
        reader = MemoryReader(pid)
    except Exception as e:
        print(f"Error attaching to process: {e}", file=sys.stderr)
        sys.exit(1)
        
    logger = StateLogger()
    aggregator = IntelligenceAggregator(pregame_spread=-5.5, live_odds=-110, pregame_total=224.5)
    
    print("Initializing Intelligence Subsystems...")
    aggregator.train_models()
    
    signal_file = Path("data") / "signal_current.json"
    
    print(f"Logging to {logger.log_file}")
    print("\n--- LIVE SCOREBOARD ---")
    
    states_logged = 0
    poll_interval = 0.5
    
    try:
        recent_alerts = []
        while True:
            # Poll state
            state = reader.read_state()
            if not state:
                if signal_file.exists():
                    signal_file.unlink()
                print("\nProcess lost. Game closed?")
                break
                
            logger.log(state)
            states_logged += 1
            
            snapshot = aggregator.process_state(state)
            
            signal_data = asdict(snapshot)
            signal_data["recent_alerts"] = [] # Deprecating array for top_alert string 
            
            with open(signal_file, "w") as f:
                f.write(json.dumps(signal_data))
                
            # Print live scoreboard
            clock_str = format_clock(state.clock)
            poss_str = "HOME" if state.possession == 0 else "AWAY"
            
            out_str = f"Q{state.quarter} | {clock_str} | HOME: {state.home_score} - AWAY: {state.away_score} | POSS: {poss_str}\n"
            out_str += f"WIN PROB: {snapshot.win_prob*100:.1f}% HOME | LIVE SPREAD: {snapshot.live_spread:+.1f} | PACE: {snapshot.pace} | SCRIPT: {snapshot.game_script}\n"
            out_str += f"EDGE: {snapshot.value_bet['edge']*100:.1f}% ({snapshot.value_bet['recommendation']}) | MOMENTUM REVERSAL: {snapshot.momentum_reversal*100:.1f}%\n"
            if snapshot.is_clutch:
                out_str += f"[CLUTCH] {snapshot.clutch_intensity:.0f} INTENSITY\n"
            if snapshot.top_alert:
                out_str += f"[ALERT] {snapshot.top_alert}\n"
                
            sys.stdout.write(out_str)
            sys.stdout.flush()
            
            time.sleep(poll_interval)
            
    except KeyboardInterrupt:
        print("\n\nSimulation interrupted by user.")
        
    print(f"\nSession summary: {states_logged} states logged.")

if __name__ == "__main__":
    main()
