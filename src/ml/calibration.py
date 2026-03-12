import json
import numpy as np
from pathlib import Path
from sklearn.linear_model import LogisticRegression


class CalibrationEngine:
    def __init__(self, history_file=None):
        self.history = []  # list of (predicted_prob, actual_outcome)
        self.scaler = None
        self.history_file = history_file or Path("data") / "calibration_history.jsonl"
        self._load_history()

    def _load_history(self):
        if Path(self.history_file).exists():
            with open(self.history_file, "r") as f:
                for line in f:
                    rec = json.loads(line.strip())
                    self.history.append((rec["predicted"], rec["actual"]))
            if len(self.history) >= 50:
                self.recalibrate()

    def _save_entry(self, predicted, actual):
        Path(self.history_file).parent.mkdir(parents=True, exist_ok=True)
        with open(self.history_file, "a") as f:
            f.write(json.dumps({"predicted": predicted, "actual": actual}) + "\n")

    def log_outcome(self, predicted: float, actual_won: bool):
        self.history.append((predicted, int(actual_won)))
        self._save_entry(predicted, int(actual_won))
        if len(self.history) >= 50:
            self.recalibrate()

    def recalibrate(self):
        X = np.array([h[0] for h in self.history]).reshape(-1, 1)
        y = np.array([h[1] for h in self.history])

        # Need at least 2 classes to fit
        if len(set(y)) < 2:
            return

        self.scaler = LogisticRegression(max_iter=1000)
        self.scaler.fit(X, y)

    def calibrate(self, raw_prob: float) -> float:
        if self.scaler is None:
            return raw_prob
        return float(self.scaler.predict_proba([[raw_prob]])[0][1])

    def brier_score(self) -> float:
        if len(self.history) < 10:
            return None
        preds = [h[0] for h in self.history]
        acts = [h[1] for h in self.history]
        return sum((p - a) ** 2 for p, a in zip(preds, acts)) / len(self.history)

    def accuracy_report(self) -> dict:
        bs = self.brier_score()
        return {
            "games_tracked": len(self.history),
            "brier_score": bs,
            "target": 0.18,
            "beating_espn_bpi": bs < 0.21 if bs is not None else False,
        }
