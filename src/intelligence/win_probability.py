import math
import json
import joblib
import numpy as np
from pathlib import Path
from sklearn.ensemble import RandomForestClassifier
from src.simulation.memory_reader import GameState

class WinProbabilityModel:
    MODEL_PATH = Path("data/models/win_prob_rf.pkl")
    TRAIN_DATA = Path("data/synthetic/games_10k.jsonl")

    def __init__(self):
        self.rf_model = None
        self._load_model()
        self.possessions_elapsed = 0
        self.last_possession = None

    def _load_model(self):
        if self.MODEL_PATH.exists():
            try:
                self.rf_model = joblib.load(self.MODEL_PATH)
            except Exception as e:
                print(f"Error loading model: {e}")

    def calculate_time_remaining(self, state: GameState) -> float:
        q = state.quarter if state.quarter <= 4 else 4
        return max(0, ((4 - q) * 720) + state.clock)

    def calculate_time_elapsed(self, state: GameState) -> float:
        return (4 * 720) - self.calculate_time_remaining(state)

    def _extract_features(self, state: GameState, momentum=0.0) -> list:
        time_rem = self.calculate_time_remaining(state)
        time_elap = self.calculate_time_elapsed(state)
        
        score_diff = state.home_score - state.away_score
        home_rate = (state.home_score / time_elap * 60) if time_elap > 0 else 0.0
        away_rate = (state.away_score / time_elap * 60) if time_elap > 0 else 0.0

        return [
            score_diff,
            time_rem,
            state.quarter,
            momentum,
            home_rate,
            away_rate
        ]

    def _logistic_fallback(self, state: GameState) -> float:
        time_remaining = self.calculate_time_remaining(state)
        score_diff = state.home_score - state.away_score
        z = (score_diff * 0.15) + ((time_remaining / 60) * -0.002)
        return 1 / (1 + math.exp(-z))

    def __call__(self, state: GameState, momentum=0.0) -> float:
        if self.rf_model is not None:
            try:
                features = np.array([self._extract_features(state, momentum)])
                return float(self.rf_model.predict_proba(features)[0][1])
            except Exception:
                pass
        return self._logistic_fallback(state)

    @classmethod
    def train(cls, games: list = None):
        X, y = [], []
        # We need a model instance for the instance methods
        model_inst = cls.__new__(cls)
        
        class DummyState:
            def __init__(self, d):
                self.quarter = d["quarter"]
                self.clock = d["clock"]
                self.home_score = d["home_score"]
                self.away_score = d["away_score"]

        if games is None:
            if not cls.TRAIN_DATA.exists():
                print(f"Training data not found: {cls.TRAIN_DATA}")
                return
            print(f"Loading and processing data from {cls.TRAIN_DATA}...")
            # Open and read line by line to save memory
            with open(cls.TRAIN_DATA, "r") as f:
                games_iter = (json.loads(line) for line in f)
                X, y = cls._process_games(games_iter, model_inst, DummyState)
        else:
            X, y = cls._process_games(games, model_inst, DummyState)

        if not X:
            return

        print(f"Training RandomForest on {len(X)} samples...")
        X = np.array(X, dtype=np.float32)
        y = np.array(y, dtype=np.int8)

        rf = RandomForestClassifier(n_estimators=100, max_depth=10, n_jobs=-1, random_state=42)
        rf.fit(X, y)

        # Basic AUC check on training data for the test suite
        from sklearn.metrics import roc_auc_score
        probs = rf.predict_proba(X)[:, 1]
        cls._last_auc = float(roc_auc_score(y, probs))

        cls.MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(rf, cls.MODEL_PATH)
        print(f"Model saved to {cls.MODEL_PATH} (AUC: {cls._last_auc:.3f})")

    @staticmethod
    def _process_games(games_iter, model_inst, state_cls):
        X, y = [], []
        for game in games_iter:
            home_won = 1 if game["final_home"] > game["final_away"] else 0
            for i, s_dict in enumerate(game["states"]):
                if i % 10 != 0:
                    continue
                feat = model_inst._extract_features(state_cls(s_dict), s_dict.get("momentum", 0.0))
                X.append(feat)
                y.append(home_won)
        return X, y

    def projected_score(self, state: GameState):
        time_elapsed = self.calculate_time_elapsed(state)
        time_remaining = self.calculate_time_remaining(state)
        
        # Simple pace-based projection
        if time_elapsed <= 0:
            return state.home_score, state.away_score
            
        home_rate = state.home_score / time_elapsed
        away_rate = state.away_score / time_elapsed
        
        proj_home = state.home_score + (home_rate * time_remaining)
        proj_away = state.away_score + (away_rate * time_remaining)
        return int(proj_home), int(proj_away)
