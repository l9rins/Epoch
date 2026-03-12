import json
import numpy as np
from sklearn.linear_model import LogisticRegression
from src.ml.scoring_run_predictor import load_synthetic_data

class ComebackEngine:
    def __init__(self):
        self.model = LogisticRegression(max_iter=1000)
        self.is_trained = False
        
    def extract_features(self, state, previous_states=None):
        score_diff = state["home_score"] - state["away_score"]
        time_remaining = state["time_remaining"]
        momentum_trend = 0.0
        
        poss_eff = 0.0
        if state["home_score"] + state["away_score"] > 0 and state.get("possession_count", 1) > 0:
            poss_eff = (state["home_score"] + state["away_score"]) / max(1, state.get("possession_count", 1))
            
        return [score_diff, time_remaining, momentum_trend, poss_eff]
        
    def train(self, games):
        X = []
        y = []
        for game in games:
            states = game["states"]
            final_home = game["final_home"]
            final_away = game["final_away"]
            
            for state in states:
                # We only care about comeback situations
                score_diff = state["home_score"] - state["away_score"]
                if abs(score_diff) < 5: 
                    continue # Not a significant comeback situation
                    
                target = 1 if final_home > final_away else 0
                
                # if home is trailing, a comeback is if target == 1
                # if away is trailing, a comeback is if target == 0
                is_comeback = (score_diff < 0 and target == 1) or (score_diff > 0 and target == 0)
                
                X.append(self.extract_features(state))
                # For training simplicity, we just train a model that predicts home win prob
                # from which we can derive the comeback prob
                y.append(target)
                
        if X and y and len(set(y)) > 1:
            self.model.fit(X, y)
            self.is_trained = True
            
    def predict(self, state) -> float:
        if not self.is_trained:
            return 0.0
        features = np.array([self.extract_features(state)])
        home_win_prob = float(self.model.predict_proba(features)[0][1])
        
        score_diff = state["home_score"] - state["away_score"]
        if score_diff < 0:
            return home_win_prob # Home trailing, probability of home win
        else:
            return 1.0 - home_win_prob # Away trailing, probability of away win


if __name__ == "__main__":
    games = load_synthetic_data(max_games=200)
    engine = ComebackEngine()
    engine.train(games)
    print(f"Comeback Engine trained: {engine.is_trained}")
