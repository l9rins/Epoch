import time
from dataclasses import dataclass, asdict
from src.simulation.memory_reader import GameState
from src.intelligence.win_probability import WinProbabilityModel
from src.intelligence.momentum import MomentumTracker
from src.intelligence.signal_alerts import AlertEngine
from src.ml.scoring_run_predictor import ScoringRunPredictor, load_synthetic_data
from src.ml.comeback_engine import ComebackEngine
from src.ml.pace_classifier import PaceClassifier
from src.ml.clutch_detector import ClutchDetector, ClutchState
from src.ml.quarter_trajectory import QuarterTrajectory
from src.ml.spread_calculator import SpreadCalculator
from src.ml.total_forecaster import TotalForecaster
from src.ml.momentum_reversal import MomentumReversal
from src.ml.game_script import GameScriptClassifier
from src.ml.value_detector import ValueDetector, ValueBet

@dataclass
class IntelligenceSnapshot:
    timestamp: float
    game_state: dict
    win_prob: float
    comeback_prob: float
    pace: str
    is_clutch: bool
    clutch_intensity: float
    live_spread: float
    projected_total: int
    over_prob: float
    momentum_reversal: float
    game_script: str
    value_bet: dict
    top_alert: str

class IntelligenceAggregator:
    def __init__(self, pregame_spread=-4.5, live_odds=-110, pregame_total=224.5):
        self.pregame_spread = pregame_spread
        self.live_odds = live_odds
        
        # Base Phase 6 Systems
        self.win_model = WinProbabilityModel()
        self.momentum_tracker = MomentumTracker()
        self.alert_engine = AlertEngine()
        
        # ML Phase 7 Systems
        self.scoring_run = ScoringRunPredictor()
        self.comeback = ComebackEngine()
        self.pace = PaceClassifier()
        self.clutch = ClutchDetector()
        self.qt = QuarterTrajectory()
        self.spread = SpreadCalculator(pregame_spread=pregame_spread)
        self.total = TotalForecaster(pregame_total=pregame_total)
        self.reversal = MomentumReversal()
        self.script = GameScriptClassifier()
        self.value = ValueDetector()
        
        self.state_history = []
        self._is_ready = False
        
    def train_models(self):
        print("Aggregator: Loading synthetic training data (500 games)...")
        try:
            games = load_synthetic_data(max_games=500) # train on 500 games for speed
            print("Aggregator: Precompiling model states...")
            
            self.scoring_run.train(games)
            self.comeback.train(games)
            self.pace.train(games)
            self.total.train(games)
            self.reversal.train(games)
            self.script.train(games)
            
            self._is_ready = True
            print("Aggregator: All ML models loaded and active.")
        except FileNotFoundError:
            print("WARNING: Synthetic data not found. Run src/ml/data_generator.py first. Models will fallback to defaults.")
            self._is_ready = False
            
    def process_state(self, state: GameState) -> IntelligenceSnapshot:
        if not self._is_ready:
            self.train_models()
        
        # Convert state object to dict expected by ML models
        s_dict = {
            "quarter": state.quarter,
            "clock": state.clock,
            "home_score": state.home_score,
            "away_score": state.away_score,
            "possession": state.possession,
            "time_remaining": self.win_model.calculate_time_remaining(state)
        }
        
        # Layer 1 computing
        momentum_score = self.momentum_tracker(state)
        s_dict["momentum"] = momentum_score
        
        if len(self.state_history) > 0:
            last_s = self.state_history[-1]
            pts_this_poss = max(
                (state.home_score - last_s["home_score"]),
                (state.away_score - last_s["away_score"])
            )
            if state.possession != last_s["possession"]:
                s_dict["pts_scored_this_poss"] = pts_this_poss
                s_dict["possession_count"] = last_s.get("possession_count", 0) + 1
            else:
                s_dict["pts_scored_this_poss"] = 0
                s_dict["possession_count"] = last_s.get("possession_count", 0)
        else:
            s_dict["pts_scored_this_poss"] = 0
            s_dict["possession_count"] = 1
            
        self.state_history.append(s_dict)
        if len(self.state_history) > 500: # ~250 mins max
            self.state_history.pop(0)

        # Base outputs
        win_prob = self.win_model(state)
        proj_home, proj_away = self.win_model.projected_score(state)
        game_time = self.momentum_tracker._game_time(state)
        alerts = self.alert_engine.process(game_time, win_prob, momentum_score, proj_home, proj_away)
        
        top_alert = alerts[-1].message if alerts else ""
        
        # ML outputs
        comeback_p = self.comeback.predict(s_dict)
        pace_res = self.pace.predict(s_dict, self.state_history[:-1])
        clutch_state = self.clutch.detect(s_dict, self.state_history[:-1])
        qt_res = self.qt.analyze(s_dict, self.state_history[:-1])
        spread_val = self.spread.calculate(s_dict, momentum_score, pace_res["projected_total"])
        total_res = self.total.predict(s_dict, self.state_history[:-1])
        rev_prob = self.reversal.predict(s_dict, self.state_history[:-1])
        script_res = self.script.predict(s_dict, self.state_history[:-1])
        value_res = self.value.detect(win_prob, self.live_odds)
        
        return IntelligenceSnapshot(
            timestamp=time.time(),
            game_state=s_dict,
            win_prob=win_prob,
            comeback_prob=comeback_p,
            pace=pace_res["pace"],
            is_clutch=clutch_state.is_clutch,
            clutch_intensity=clutch_state.intensity,
            live_spread=spread_val,
            projected_total=total_res["projected_total"],
            over_prob=total_res["over_prob"],
            momentum_reversal=rev_prob,
            game_script=script_res["script"],
            value_bet=asdict(value_res),
            top_alert=top_alert
        )
