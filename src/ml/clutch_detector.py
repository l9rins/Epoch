from dataclasses import dataclass
from src.ml.scoring_run_predictor import load_synthetic_data

@dataclass
class ClutchState:
    is_clutch: bool
    clutch_type: str
    intensity: float
    recommendation: str

class ClutchDetector:
    def __init__(self):
        # A deterministic model based on specific game states as defined
        pass
        
    def detect(self, state, previous_states=None) -> ClutchState:
        time_rem = state["time_remaining"]
        score_diff = abs(state["home_score"] - state["away_score"])
        momentum = abs(state.get("momentum", 0.0))
        
        is_q4_ot = state["quarter"] >= 4
        is_close = score_diff <= 5
        is_late = time_rem <= 300 # under 5 mins
        
        # Base clutch "SCORE"
        if is_q4_ot and is_close and is_late:
            intensity = min(100.0, 50.0 + (300 - time_rem) / 6.0 + (5 - score_diff) * 10)
            return ClutchState(True, "SCORE", intensity, "HIGH VALUE BETTING WINDOW")
            
        # Momentum clutch: Team on big run entering a relatively close game late
        if is_q4_ot and momentum >= 40.0 and score_diff <= 10:
            intensity = min(100.0, 40.0 + (momentum - 40) + (10 - score_diff) * 5)
            return ClutchState(True, "MOMENTUM", intensity, "MOMENTUM SWING ALERT")
            
        return ClutchState(False, "NONE", 0.0, "NO EDGE")


if __name__ == "__main__":
    detector = ClutchDetector()
    sample = {"quarter": 4, "time_remaining": 120, "home_score": 100, "away_score": 98, "momentum": 10.0}
    res = detector.detect(sample)
    print(f"Sample Clutch Check: {res}")
