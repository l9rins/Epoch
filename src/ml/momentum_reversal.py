import numpy as np
from sklearn.linear_model import LogisticRegression
from src.ml.scoring_run_predictor import load_synthetic_data

class MomentumReversal:
    def __init__(self):
        self.model = LogisticRegression(max_iter=1000)
        self.is_trained = False
        
    def extract_features(self, state, previous_states=None):
        momentum = state.get("momentum", 0.0)
        score_diff = state["home_score"] - state["away_score"]
        time_rem = state["time_remaining"]
        
        momentum_slope = 0.0
        momentum_duration = 0.0
        possession_streak = 0
        
        if previous_states and len(previous_states) > 0:
            past_momentum = previous_states[0].get("momentum", 0.0)
            momentum_slope = momentum - past_momentum
            
            # Simplified possession streak
            last_poss = state["possession"]
            for s in reversed(previous_states):
                if s["possession"] == last_poss:
                    possession_streak += 1
                else:
                    break
                    
        return [momentum, momentum_slope, momentum_duration, score_diff, time_rem, possession_streak]
        
    def train(self, games):
        X = []
        y = []
        for game in games:
            states = game["states"]
            for i in range(10, len(states) - 10):
                curr_state = states[i]
                curr_momentum = curr_state.get("momentum", 0.0)
                
                # We only care if there is momentum to reverse
                if abs(curr_momentum) < 30:
                    continue
                    
                target_time = curr_state["time_remaining"] - 90
                
                reversed_flag = 0
                for j in range(i+1, len(states)):
                    if states[j]["time_remaining"] < target_time:
                        break
                        
                    future_momentum = states[j].get("momentum", 0.0)
                    
                    if curr_momentum > 0 and future_momentum < 10:
                        reversed_flag = 1
                        break
                    if curr_momentum < 0 and future_momentum > -10:
                        reversed_flag = 1
                        break
                        
                X.append(self.extract_features(curr_state, states[:i]))
                y.append(reversed_flag)
                
        if X and y and len(set(y)) > 1:
            self.model.fit(X, y)
            self.is_trained = True
            
    def predict(self, state, previous_states=None) -> float:
        if not self.is_trained:
            return 0.0
            
        features = np.array([self.extract_features(state, previous_states)])
        return float(self.model.predict_proba(features)[0][1])


if __name__ == "__main__":
    games = load_synthetic_data(max_games=200)
    reversal = MomentumReversal()
    reversal.train(games)
    print(f"Momentum Reversal trained: {reversal.is_trained}")
