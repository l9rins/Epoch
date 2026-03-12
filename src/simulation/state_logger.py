import json
import os
from datetime import datetime
from typing import Optional
from src.simulation.memory_reader import GameState


class StateLogger:
    def __init__(self, log_dir: str = "data/sim_logs"):
        self.log_dir = log_dir
        os.makedirs(self.log_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.log_file = os.path.join(self.log_dir, f"{timestamp}.jsonl")
        self.tick_count = 0
        self.first_timestamp = None
        self.last_state = None
        self.last_analytics = None

    def log(self, state: GameState):
        """Backward-compatible basic state logging (6 fields)."""
        state_dict = {
            "timestamp": state.timestamp,
            "quarter": state.quarter,
            "clock": round(state.clock, 2),
            "home_score": state.home_score,
            "away_score": state.away_score,
            "possession": state.possession
        }
        self._write(state_dict)
        self._track(state)

    def log_enriched(
        self,
        state: GameState,
        win_probability: Optional[float] = None,
        momentum: Optional[float] = None,
        projected_home: Optional[int] = None,
        projected_away: Optional[int] = None,
        home_scoring_rate: Optional[float] = None,
        away_scoring_rate: Optional[float] = None,
        game_time_elapsed: Optional[float] = None,
    ):
        """Log raw state + computed analytics in a single JSONL line."""
        score_diff = state.home_score - state.away_score

        state_dict = {
            # Raw state
            "timestamp": state.timestamp,
            "quarter": state.quarter,
            "clock": round(state.clock, 2),
            "home_score": state.home_score,
            "away_score": state.away_score,
            "possession": state.possession,
            # Computed analytics
            "win_probability": round(win_probability, 4) if win_probability is not None else None,
            "momentum": round(momentum, 2) if momentum is not None else None,
            "projected_home": projected_home,
            "projected_away": projected_away,
            "home_scoring_rate": round(home_scoring_rate, 2) if home_scoring_rate is not None else None,
            "away_scoring_rate": round(away_scoring_rate, 2) if away_scoring_rate is not None else None,
            "game_time_elapsed": round(game_time_elapsed, 1) if game_time_elapsed is not None else None,
            "score_differential": score_diff,
        }
        self._write(state_dict)
        self._track(state, {
            "win_probability": win_probability,
            "momentum": momentum,
            "projected_home": projected_home,
            "projected_away": projected_away,
        })

    def _write(self, state_dict: dict):
        """Write a single JSONL line to the log file."""
        with open(self.log_file, "a") as f:
            f.write(json.dumps(state_dict) + "\n")
            f.flush()

    def _track(self, state: GameState, analytics: dict = None):
        """Track internal counters for summary."""
        self.tick_count += 1
        if self.first_timestamp is None:
            self.first_timestamp = state.timestamp
        self.last_state = state
        self.last_analytics = analytics

    def summary(self) -> dict:
        """Return end-of-game summary stats."""
        if self.last_state is None:
            return {"ticks": 0}

        duration = self.last_state.timestamp - self.first_timestamp if self.first_timestamp else 0.0
        result = {
            "ticks": self.tick_count,
            "duration_seconds": round(duration, 1),
            "final_quarter": self.last_state.quarter,
            "final_home_score": self.last_state.home_score,
            "final_away_score": self.last_state.away_score,
            "winner": "HOME" if self.last_state.home_score > self.last_state.away_score
                      else "AWAY" if self.last_state.away_score > self.last_state.home_score
                      else "TIE",
            "log_file": self.log_file,
        }

        if self.last_analytics:
            result["final_win_probability"] = self.last_analytics.get("win_probability")
            result["final_momentum"] = self.last_analytics.get("momentum")

        return result
