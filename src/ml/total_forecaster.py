import numpy as np
from sklearn.linear_model import LinearRegression
from src.ml.scoring_run_predictor import load_synthetic_data

class TotalForecaster:
    def __init__(self, pregame_total=224.5):
        self.model = LinearRegression()
        self.is_trained = False
        self.pregame_total = pregame_total
        
        # Q1: 24%, Q2: 26%, Q3: 24%, Q4: 26%
        self.q_weights = {1: 0.24, 2: 0.26, 3: 0.24, 4: 0.26}
        
    def extract_features(self, state, previous_states=None):
        current_total = state["home_score"] + state["away_score"]
        time_rem = state["time_remaining"]
        q = min(4, state["quarter"])
        
        # Scoring rate last 5 min
        recent_pts = 0
        if previous_states:
            for s in reversed(previous_states):
                if state["time_remaining"] - s["time_remaining"] > -300: # Actually past states have higher time_remaining
                    pass
                if s["time_remaining"] - state["time_remaining"] > 300:
                    break
                # simplified: we just check total points diff in last 5 min window
                
            past_s = next((s for s in previous_states if s["time_remaining"] - state["time_remaining"] >= 300), None)
            if past_s:
                recent_pts = current_total - (past_s["home_score"] + past_s["away_score"])
                
        return [current_total, time_rem, q, recent_pts]

    def train(self, games):
        X = []
        y = []
        for game in games:
            states = game["states"]
            final_total = game["final_home"] + game["final_away"]
            
            for i, state in enumerate(states):
                X.append(self.extract_features(state, states[:i]))
                y.append(final_total)
                
        if X and y:
            self.model.fit(X, y)
            self.is_trained = True

    def predict(self, state, previous_states=None) -> dict:
        current_total = state["home_score"] + state["away_score"]
        
        if not self.is_trained:
            # simple math fallback
            time_rem = state["time_remaining"]
            time_elapsed = 2880 - time_rem
            if time_elapsed == 0:
                proj = self.pregame_total
            else:
                proj = current_total + (current_total / time_elapsed) * time_rem
            
            return {
                "projected_total": int(proj),
                "over_prob": 0.5 if proj == self.pregame_total else (0.6 if proj > self.pregame_total else 0.4),
                "under_prob": 0.5 if proj == self.pregame_total else (0.4 if proj > self.pregame_total else 0.6),
                "confidence": 0.0
            }
            
        features = np.array([self.extract_features(state, previous_states)])
        proj_total = self.model.predict(features)[0]
        
        # Blending with pregame total (anchoring)
        time_elapsed = 2880 - state["time_remaining"]
        weight = min(1.0, time_elapsed / 2880.0)
        
        blended = (proj_total * weight) + (self.pregame_total * (1 - weight))
        
        # Basic logistic curve for over/under prob around the pregame total
        z = (blended - self.pregame_total) * 0.15
        over_prob = 1 / (1 + np.exp(-z))
        
        return {
            "projected_total": int(blended),
            "over_prob": float(over_prob),
            "under_prob": float(1.0 - over_prob),
            "confidence": min(1.0, weight + 0.2)
        }

if __name__ == "__main__":
    games = load_synthetic_data(max_games=200)
    forecaster = TotalForecaster()
    forecaster.train(games)
    print(f"Total Forecaster trained: {forecaster.is_trained}")
