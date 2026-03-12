import json
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from src.ml.scoring_run_predictor import load_synthetic_data

class PaceClassifier:
    def __init__(self):
        self.model = RandomForestClassifier(n_estimators=100, max_depth=5)
        self.is_trained = False
        
    def extract_features(self, state, previous_states=None):
        # Current pace logic requires looking at how many possessions happened over time elapsed
        poss = state.get("possession_count", 1)
        time_elapsed = 2880 - state["time_remaining"]
        
        poss_per_minute = 0.0
        if time_elapsed > 0:
            poss_per_minute = (poss / time_elapsed) * 60.0
            
        scoring_rate = 0.0
        if time_elapsed > 0:
            scoring_rate = ((state["home_score"] + state["away_score"]) / time_elapsed) * 60.0
            
        return [poss_per_minute, scoring_rate]
        
    def train(self, games):
        X = []
        y = []
        for game in games:
            states = game["states"]
            
            # Label pace of game based on total possessions
            # But we generated possessions sequentially!
            total_poss = max(1, len(states)) # approx possessions
            # For 48 mins (192 poss is 2 * 96). 
            if total_poss < 180: # < 90/team
                label = "SLOW"
            elif total_poss > 200: # > 100/team
                label = "FAST"
            else:
                label = "MEDIUM"
                
            for state in states:
                # We need states past Q1 ideally
                if state["time_remaining"] < 2160: # 1 quarter elapsed
                    X.append(self.extract_features(state))
                    y.append(label)
                
        if X and y:
            self.model.fit(X, y)
            self.is_trained = True
            
    def predict(self, state, previous_states=None) -> dict:
        if not self.is_trained:
            return {"pace": "MEDIUM", "confidence": 0.0, "projected_total": 220}
            
        features = np.array([self.extract_features(state, previous_states)])
        proba = self.model.predict_proba(features)[0]
        pace_idx = np.argmax(proba)
        classes = self.model.classes_
        
        pace = str(classes[pace_idx])
        confidence = float(proba[pace_idx])
        
        # Calculate a projected total based on Pace label
        if pace == "SLOW":
            proj = 195
        elif pace == "FAST":
            proj = 240
        else:
            proj = 220
            
        return {"pace": pace, "confidence": confidence, "projected_total": proj}


if __name__ == "__main__":
    games = load_synthetic_data(max_games=200)
    classifier = PaceClassifier()
    classifier.train(games)
    print(f"Pace Classifier trained: {classifier.is_trained}")
