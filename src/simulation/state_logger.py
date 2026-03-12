import json
import os
from datetime import datetime
from src.simulation.memory_reader import GameState

class StateLogger:
    def __init__(self, log_dir: str = "data/sim_logs"):
        self.log_dir = log_dir
        os.makedirs(self.log_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.log_file = os.path.join(self.log_dir, f"{timestamp}.jsonl")
        
    def log(self, state: GameState):
        state_dict = {
            "timestamp": state.timestamp,
            "quarter": state.quarter,
            "clock": round(state.clock, 2),
            "home_score": state.home_score,
            "away_score": state.away_score,
            "possession": state.possession
        }
        with open(self.log_file, "a") as f:
            f.write(json.dumps(state_dict) + "\n")
            f.flush()
