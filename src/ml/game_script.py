import numpy as np
from sklearn.ensemble import RandomForestClassifier
from src.ml.scoring_run_predictor import load_synthetic_data

class GameScriptClassifier:
    def __init__(self):
        self.model = RandomForestClassifier(n_estimators=100, max_depth=6)
        self.is_trained = False
        
    def extract_features(self, state, previous_states=None):
        time_elapsed = 2880 - state["time_remaining"]
        score_diff = state["home_score"] - state["away_score"]
        current_total = state["home_score"] + state["away_score"]
        
        scoring_rate = 0.0
        if time_elapsed > 0:
            scoring_rate = (current_total / time_elapsed) * 60.0
            
        momentum = state.get("momentum", 0.0)
        
        return [time_elapsed, score_diff, current_total, scoring_rate, momentum]
        
    def label_game(self, game) -> str:
        final_home = game["final_home"]
        final_away = game["final_away"]
        states = game["states"]
        
        diff = final_home - final_away
        total = final_home + final_away
        
        # Simple heuristics for labeling synthetic games
        if diff >= 20: return "BLOWOUT_HOME"
        if diff <= -20: return "BLOWOUT_AWAY"
        if total >= 240 and abs(diff) < 10: return "SHOOTOUT"
        if total <= 190 and abs(diff) < 10: return "GRIND"
        
        # Comeback detected?
        max_home_lead = 0
        max_away_lead = 0
        for s in states:
            d = s["home_score"] - s["away_score"]
            if d > max_home_lead: max_home_lead = d
            if d < max_away_lead: max_away_lead = d
            
        if diff > 0 and abs(max_away_lead) >= 15: return "COMEBACK"
        if diff < 0 and max_home_lead >= 15: return "COMEBACK"
        
        return "BACK_AND_FORTH"
        
    def train(self, games):
        X = []
        y = []
        for game in games:
            label = self.label_game(game)
            states = game["states"]
            
            for state in states:
                # We want the classifier to learn mid-game what the script is
                # Skip Q1 for better signal later on
                if state["quarter"] > 1:
                    X.append(self.extract_features(state))
                    y.append(label)
                    
        if X and y:
            self.model.fit(X, y)
            self.is_trained = True
            
    def predict(self, state, previous_states=None) -> dict:
        if not self.is_trained:
            return {"script": "BACK_AND_FORTH", "confidence": 0.0, "betting_implication": "UNKNOWN"}
            
        features = np.array([self.extract_features(state, previous_states)])
        proba = self.model.predict_proba(features)[0]
        idx = np.argmax(proba)
        
        script = str(self.model.classes_[idx])
        conf = float(proba[idx])
        
        imp = "LIVE SPREAD UNSTABLE"
        if "BLOWOUT" in script:
            imp = "AVOID SPREADS, LOOK AT PLAYER PROPS"
        elif script == "SHOOTOUT":
            imp = "HIGH VALUE ON OVERS IN Q4"
        elif script == "GRIND":
            imp = "UNDERS ARE SAFER"
        elif script == "COMEBACK":
            imp = "MONEYLINE VALUE ON TRAILING TEAM"
            
        return {"script": script, "confidence": conf, "betting_implication": imp}

if __name__ == "__main__":
    games = load_synthetic_data(max_games=200)
    script_classifier = GameScriptClassifier()
    script_classifier.train(games)
    print(f"Game Script Classifier trained: {script_classifier.is_trained}")
