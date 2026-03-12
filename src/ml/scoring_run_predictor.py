import json
from pathlib import Path
import numpy as np
from sklearn.linear_model import LogisticRegression

def load_synthetic_data(file_path="data/synthetic/games_10k.jsonl", max_games=None):
    games = []
    with open(file_path, "r") as f:
        for i, line in enumerate(f):
            if max_games and i >= max_games:
                break
            games.append(json.loads(line))
    return games

class ScoringRunPredictor:
    def __init__(self):
        self.model = LogisticRegression(max_iter=1000)
        self.is_trained = False
        
    def extract_features(self, state, previous_states):
        # Features: current momentum, possession count, score differential, quarter, time remaining
        # Last 10 possession outcomes (points scored)
        momentum = state.get("momentum", 0.0) # We might need to compute this if not in raw state
        score_diff = state["home_score"] - state["away_score"]
        possession = state["possession"]
        
        last_10 = [0] * 10
        for i, s in enumerate(previous_states[-10:]):
            last_10[-(i+1)] = s.get("pts_scored_this_poss", 0)
            
        features = [
            momentum,
            possession,
            score_diff,
            state["quarter"],
            state["time_remaining"],
            sum(last_10) # Total points in last 10
        ] + last_10
        return features
        
    def train(self, games):
        X = []
        y = []
        for game in games:
            states = game["states"]
            for i in range(10, len(states) - 10):
                # Is there a run of 5+ unanswered in the next 2 mins?
                curr_state = states[i]
                target_time = curr_state["time_remaining"] - 120
                
                # Look ahead for a run
                run_achieved = 0
                home_pts = 0
                away_pts = 0
                
                for j in range(i+1, len(states)):
                    if states[j]["time_remaining"] < target_time:
                        break
                        
                    home_pts += (states[j]["home_score"] - states[j-1]["home_score"])
                    away_pts += (states[j]["away_score"] - states[j-1]["away_score"])
                    
                    if home_pts >= 5 and away_pts == 0:
                        run_achieved = 1
                        break
                    if away_pts >= 5 and home_pts == 0:
                        run_achieved = 1
                        break
                        
                    if home_pts > 0 and away_pts > 0:
                        # streak broken for both
                        home_pts = 0
                        away_pts = 0
                        
                X.append(self.extract_features(curr_state, states[:i]))
                y.append(run_achieved)
                
        if X and y and len(set(y)) > 1:
            self.model.fit(X, y)
            self.is_trained = True
            
    def predict(self, state, previous_states) -> float:
        if not self.is_trained:
            return 0.0
        features = np.array([self.extract_features(state, previous_states)])
        return float(self.model.predict_proba(features)[0][1])

if __name__ == "__main__":
    games = load_synthetic_data(max_games=200) # subset for speed
    predictor = ScoringRunPredictor()
    predictor.train(games)
    print(f"Scoring Run Predictor trained: {predictor.is_trained}")
