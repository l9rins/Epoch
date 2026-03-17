"""
aggregator.py — Epoch Engine v2
9-model ensemble aggregator.

Vote slots:
    1. RandomForest (calibrated)         weight 0.18  — trained on synthetic + real data
    2. XGBoost/GBM (calibrated)          weight 0.18  — trained on synthetic + real data
    3. Elo (pure historical)             weight 0.10  — stable baseline, doesn't overfit
    4. Fatigue model                     weight 0.12  — schedule density + travel + altitude
    5. Referee model                     weight 0.08  — crew home-bias + foul-rate
    6. Momentum (live, in-game only)     weight 0.12  — rolling possession momentum
    7. Spread calculator                 weight 0.10  — live spread → implied probability
    8. Transformer (stub → full later)   weight 0.06  — sequential game-state model
    9. GNN (stub → full later)           weight 0.06  — knowledge graph embeddings

Total = 1.00. Weights are confidence-adjusted at runtime (low-confidence votes
are down-weighted and the slack redistributed proportionally to high-confidence).

Upgrade from v1:
    - v1: IntelligenceAggregator with 12 ML models, no unified vote weighting
    - v2: Explicit 9-vote system with per-vote confidence gating, disagreement
          detection, and ensemble_meta output for scouting report consumption
"""

from __future__ import annotations

import time
from dataclasses import dataclass, asdict, field
from typing import Optional

from src.simulation.memory_reader import GameState
from src.intelligence.win_probability import WinProbabilityModel
from src.intelligence.momentum import MomentumTracker
from src.intelligence.signal_alerts import AlertEngine
from src.intelligence.fatigue_model import FatigueModel, TeamScheduleSnapshot
from src.intelligence.referee_model import RefereeModel
from src.ml.scoring_run_predictor import ScoringRunPredictor, load_synthetic_data
from src.ml.comeback_engine import ComebackEngine
from src.ml.pace_classifier import PaceClassifier
from src.ml.clutch_detector import ClutchDetector
from src.ml.quarter_trajectory import QuarterTrajectory
from src.ml.spread_calculator import SpreadCalculator
from src.ml.total_forecaster import TotalForecaster
from src.ml.momentum_reversal import MomentumReversal
from src.ml.game_script import GameScriptClassifier
from src.ml.value_detector import ValueDetector
from src.ml.ensemble_model import predict_single_game

import numpy as np


# ---------------------------------------------------------------------------
# Vote weight table — must sum to 1.0
# ---------------------------------------------------------------------------

BASE_WEIGHTS: dict[str, float] = {
    "random_forest":  0.18,
    "xgboost":        0.18,
    "elo":            0.10,
    "fatigue":        0.12,
    "referee":        0.08,
    "momentum":       0.12,
    "spread":         0.10,
    "transformer":    0.06,
    "gnn":            0.06,
}

# Confidence multipliers applied before renormalization
CONFIDENCE_MULTIPLIER: dict[str, float] = {
    "HIGH":   1.0,
    "MEDIUM": 0.70,
    "LOW":    0.35,
}

DISAGREEMENT_THRESHOLD = 0.15   # votes this far from ensemble mean are flagged


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class VoteRecord:
    model: str
    home_win_prob: float
    confidence: str
    weight_base: float
    weight_effective: float = 0.0
    components: dict = field(default_factory=dict)


@dataclass
class EnsembleSnapshot:
    """Full output of one aggregator.process_state() call."""
    timestamp: float
    game_state: dict

    # Core prediction
    ensemble_home_win_prob: float
    ensemble_confidence: str
    ci_lower: float
    ci_upper: float

    # Individual votes
    votes: list[VoteRecord]
    vote_agreement: float          # pct of votes within DISAGREEMENT_THRESHOLD of ensemble
    vote_disagreement_flags: list[str]   # model names that disagreed

    # Downstream intelligence (unchanged from v1)
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

    # Projected score
    proj_home: int
    proj_away: int


# ---------------------------------------------------------------------------
# Elo model (lightweight, no external dependency)
# ---------------------------------------------------------------------------

# Team Elo ratings as of 2025-26 season start.
# Pipeline can override these daily via elo_ratings.json.
DEFAULT_ELO: dict[str, float] = {
    "BOS": 1612, "OKC": 1598, "CLE": 1585, "DEN": 1574, "MIN": 1563,
    "NYK": 1557, "GSW": 1548, "MIL": 1540, "PHX": 1532, "LAC": 1524,
    "DAL": 1518, "MIA": 1510, "PHI": 1505, "IND": 1498, "LAL": 1492,
    "NOP": 1455, "SAC": 1452, "ATL": 1448, "CHI": 1443, "BRK": 1438,
    "TOR": 1432, "UTA": 1425, "MEM": 1418, "ORL": 1412, "HOU": 1408,
    "SAS": 1400, "DET": 1395, "CHA": 1388, "WAS": 1375, "POR": 1368,
}

ELO_K = 20.0          # K-factor for in-season updates
ELO_HOME_ADVANTAGE = 100.0   # Elo points added to home team


def elo_win_probability(home_team: str, away_team: str, elo_table: Optional[dict] = None) -> dict:
    """
    Pure Elo win probability. No external dependencies.
    Returns vote dict compatible with aggregator vote format.
    """
    ratings = elo_table or DEFAULT_ELO
    home_elo = ratings.get(home_team, 1500.0) + ELO_HOME_ADVANTAGE
    away_elo = ratings.get(away_team, 1500.0)
    expected = 1.0 / (1.0 + 10 ** ((away_elo - home_elo) / 400.0))
    conf = "HIGH" if home_team in ratings and away_team in ratings else "LOW"
    return {
        "model": "elo",
        "home_win_prob": round(expected, 4),
        "confidence": conf,
        "components": {"home_elo": home_elo, "away_elo": away_elo},
    }


# ---------------------------------------------------------------------------
# Transformer stub (returns neutral until model is trained)
# ---------------------------------------------------------------------------

def transformer_vote(feature_vector: Optional[np.ndarray] = None) -> dict:
    """
    Stub for sequential Transformer model.
    Replace the body with actual inference once the model is trained.
    Returns neutral 0.50 with LOW confidence so the weight is down-scaled.
    """
    return {
        "model": "transformer",
        "home_win_prob": 0.50,
        "confidence": "LOW",
        "components": {"status": "stub — train transformer before enabling"},
    }


# ---------------------------------------------------------------------------
# GNN stub (returns neutral until graph pipeline is live)
# ---------------------------------------------------------------------------

def gnn_vote(home_team: str, away_team: str) -> dict:
    """
    Stub for GNN vote. Replace with real inference once KnowledgeGraphBuilder
    has live node features from ros_reader + nba_api.
    """
    try:
        from src.graph.gnn_model import create_prediction_edge
        builder = create_prediction_edge(home_team, away_team)
        # TODO: run actual GNN inference over builder.graph
        # For now return neutral with LOW confidence
        return {
            "model": "gnn",
            "home_win_prob": 0.50,
            "confidence": "LOW",
            "components": {"status": "graph built, inference stub"},
        }
    except Exception as e:
        return {
            "model": "gnn",
            "home_win_prob": 0.50,
            "confidence": "LOW",
            "components": {"status": f"error: {e}"},
        }


# ---------------------------------------------------------------------------
# Weight normalization
# ---------------------------------------------------------------------------

def _compute_effective_weights(votes: list[VoteRecord]) -> list[VoteRecord]:
    """
    Apply confidence multipliers and renormalize weights to sum to 1.0.
    Low-confidence votes shrink; their slack is redistributed proportionally.
    """
    raw_weights = []
    for v in votes:
        mult = CONFIDENCE_MULTIPLIER.get(v.confidence, 0.35)
        raw_weights.append(v.weight_base * mult)

    total = sum(raw_weights)
    if total == 0:
        total = 1.0

    for v, rw in zip(votes, raw_weights):
        v.weight_effective = round(rw / total, 6)
    return votes


# ---------------------------------------------------------------------------
# Main aggregator
# ---------------------------------------------------------------------------

class IntelligenceAggregator:
    """
    Epoch Engine v2 Intelligence Aggregator.

    Manages all 9 vote slots, downstream ML intelligence, and produces
    EnsembleSnapshot per game tick.

    Usage:
        agg = IntelligenceAggregator(
            home_team="GSW", away_team="LAL",
            home_schedule=home_snap, away_schedule=away_snap,
            ref_names=["Scott Foster"],
            pregame_spread=-4.5,
        )
        agg.train_models()
        snapshot = agg.process_state(game_state)
    """

    def __init__(
        self,
        home_team: str = "HOME",
        away_team: str = "AWAY",
        home_schedule: Optional[TeamScheduleSnapshot] = None,
        away_schedule: Optional[TeamScheduleSnapshot] = None,
        ref_names: Optional[list[str]] = None,
        elo_table: Optional[dict] = None,
        pregame_spread: float = -4.5,
        live_odds: float = -110,
        pregame_total: float = 224.5,
    ):
        self.home_team = home_team
        self.away_team = away_team
        self.home_schedule = home_schedule
        self.away_schedule = away_schedule
        self.ref_names = ref_names or []
        self.elo_table = elo_table
        self.pregame_spread = pregame_spread
        self.live_odds = live_odds

        # Core models
        self.win_model    = WinProbabilityModel()
        self.momentum_tracker = MomentumTracker()
        self.alert_engine = AlertEngine()
        self.fatigue_model  = FatigueModel()
        self.referee_model  = RefereeModel()

        # ML suite (v1 models — unchanged, still used for downstream intelligence)
        self.scoring_run = ScoringRunPredictor()
        self.comeback    = ComebackEngine()
        self.pace        = PaceClassifier()
        self.clutch      = ClutchDetector()
        self.qt          = QuarterTrajectory()
        self.spread      = SpreadCalculator(pregame_spread=pregame_spread)
        self.total       = TotalForecaster(pregame_total=pregame_total)
        self.reversal    = MomentumReversal()
        self.script      = GameScriptClassifier()
        self.value       = ValueDetector()

        self.state_history: list[dict] = []
        self._is_ready = False

        # Pre-compute static votes (don't change during a game)
        self._static_votes = self._build_static_votes()

    # ---------------------------------------------------------------------------
    # Setup
    # ---------------------------------------------------------------------------

    def train_models(self):
        print("Aggregator v2: Loading training data...")
        try:
            games = load_synthetic_data(max_games=500)
            self.scoring_run.train(games)
            self.comeback.train(games)
            self.pace.train(games)
            self.total.train(games)
            self.reversal.train(games)
            self.script.train(games)
            self._is_ready = True
            print("Aggregator v2: All ML models ready.")
        except FileNotFoundError:
            print("WARNING: Synthetic data not found. Run data_generator.py first.")
            self._is_ready = False

    def _build_static_votes(self) -> list[VoteRecord]:
        """Pre-game static votes: Elo, Fatigue, Referee."""
        votes = []

        # Vote 3: Elo
        elo = elo_win_probability(self.home_team, self.away_team, self.elo_table)
        votes.append(VoteRecord(
            model="elo",
            home_win_prob=elo["home_win_prob"],
            confidence=elo["confidence"],
            weight_base=BASE_WEIGHTS["elo"],
            components=elo.get("components", {}),
        ))

        # Vote 4: Fatigue
        if self.home_schedule and self.away_schedule:
            home_rep = self.fatigue_model.evaluate(self.home_schedule)
            away_rep = self.fatigue_model.evaluate(self.away_schedule)
            fat_vote = self.fatigue_model.ensemble_vote(home_rep, away_rep)
        else:
            fat_vote = {"model": "fatigue", "home_win_prob": 0.50, "confidence": "LOW", "components": {}}
        votes.append(VoteRecord(
            model="fatigue",
            home_win_prob=fat_vote["home_win_prob"],
            confidence=fat_vote["confidence"],
            weight_base=BASE_WEIGHTS["fatigue"],
            components=fat_vote.get("components", {}),
        ))

        # Vote 5: Referee
        home_pace = getattr(self.home_schedule, "home_pace", 100.0) if self.home_schedule else 100.0
        away_pace = getattr(self.away_schedule, "home_pace", 100.0) if self.away_schedule else 100.0
        ref_report = self.referee_model.evaluate(self.ref_names, home_pace, away_pace)
        ref_vote   = self.referee_model.ensemble_vote(ref_report, base_home_win_prob=0.50)
        votes.append(VoteRecord(
            model="referee",
            home_win_prob=ref_vote["home_win_prob"],
            confidence=ref_vote["confidence"],
            weight_base=BASE_WEIGHTS["referee"],
            components=ref_vote.get("components", {}),
        ))

        # Vote 8: Transformer (stub)
        tf = transformer_vote()
        votes.append(VoteRecord(
            model="transformer",
            home_win_prob=tf["home_win_prob"],
            confidence=tf["confidence"],
            weight_base=BASE_WEIGHTS["transformer"],
            components=tf.get("components", {}),
        ))

        # Vote 9: GNN (stub)
        gnn = gnn_vote(self.home_team, self.away_team)
        votes.append(VoteRecord(
            model="gnn",
            home_win_prob=gnn["home_win_prob"],
            confidence=gnn["confidence"],
            weight_base=BASE_WEIGHTS["gnn"],
            components=gnn.get("components", {}),
        ))

        return votes

    # ---------------------------------------------------------------------------
    # Main per-tick method
    # ---------------------------------------------------------------------------

    def process_state(self, state: GameState) -> EnsembleSnapshot:
        if not self._is_ready:
            self.train_models()

        s_dict = {
            "quarter": state.quarter,
            "clock": state.clock,
            "home_score": state.home_score,
            "away_score": state.away_score,
            "possession": state.possession,
            "time_remaining": self.win_model.calculate_time_remaining(state),
        }

        # Rolling history
        momentum_score = self.momentum_tracker(state)
        s_dict["momentum"] = momentum_score
        self._update_history(state, s_dict)

        # --- Dynamic votes (change each tick) ---
        live_votes = list(self._static_votes)   # copy static votes

        # Vote 1: RandomForest
        # Build feature vector matching WinProbabilityModel._extract_features
        feat_vec = np.array(self.win_model._extract_features(state, momentum_score, s_dict))
        rf_result = predict_single_game(feat_vec)
        live_votes.insert(0, VoteRecord(
            model="random_forest",
            home_win_prob=rf_result["rf_probability"],
            confidence=rf_result["confidence"],
            weight_base=BASE_WEIGHTS["random_forest"],
            components={"ci_lower": rf_result["ci_lower"], "ci_upper": rf_result["ci_upper"]},
        ))

        # Vote 2: XGBoost
        live_votes.insert(1, VoteRecord(
            model="xgboost",
            home_win_prob=rf_result["xgb_probability"],
            confidence=rf_result["confidence"],
            weight_base=BASE_WEIGHTS["xgboost"],
        ))

        # Vote 6: Momentum (live)
        # Convert momentum (-100 to +100) → win probability
        raw_win = self.win_model(state, momentum_score)
        live_votes.insert(5, VoteRecord(
            model="momentum",
            home_win_prob=round(max(0.10, min(0.90, raw_win)), 4),
            confidence="HIGH" if abs(momentum_score) > 20 else "MEDIUM",
            weight_base=BASE_WEIGHTS["momentum"],
            components={"momentum_score": momentum_score},
        ))

        # Vote 7: Spread-implied probability
        spread_val = self.spread.calculate(s_dict, momentum_score, s_dict.get("time_remaining", 2880))
        # Convert spread to win probability: each point ~ 3% on normalized scale
        spread_wp = round(0.5 - spread_val * 0.03, 4)
        spread_wp = max(0.10, min(0.90, spread_wp))
        live_votes.insert(6, VoteRecord(
            model="spread",
            home_win_prob=spread_wp,
            confidence="MEDIUM",
            weight_base=BASE_WEIGHTS["spread"],
            components={"live_spread": spread_val},
        ))

        # --- Weight normalization ---
        live_votes = _compute_effective_weights(live_votes)

        # --- Ensemble probability ---
        ensemble_prob = sum(v.home_win_prob * v.weight_effective for v in live_votes)
        ensemble_prob = round(max(0.05, min(0.95, ensemble_prob)), 4)

        # --- Disagreement analysis ---
        agreement_count = sum(
            1 for v in live_votes
            if abs(v.home_win_prob - ensemble_prob) <= DISAGREEMENT_THRESHOLD
        )
        vote_agreement = round(agreement_count / len(live_votes), 3)
        disagreement_flags = [
            v.model for v in live_votes
            if abs(v.home_win_prob - ensemble_prob) > DISAGREEMENT_THRESHOLD
        ]

        # CI: base ± (1 - agreement) * 0.15
        ci_half = (1.0 - vote_agreement) * 0.15
        ci_lower = round(max(0.0, ensemble_prob - ci_half), 4)
        ci_upper = round(min(1.0, ensemble_prob + ci_half), 4)

        # Ensemble confidence
        if vote_agreement >= 0.80 and rf_result["confidence"] == "HIGH":
            ens_conf = "HIGH"
        elif vote_agreement >= 0.60:
            ens_conf = "MEDIUM"
        else:
            ens_conf = "LOW"

        # --- Downstream intelligence (unchanged from v1) ---
        proj_home, proj_away = self.win_model.projected_score(state)
        game_time = self.momentum_tracker._game_time(state)
        alerts = self.alert_engine.process(game_time, ensemble_prob, momentum_score, proj_home, proj_away)
        top_alert = alerts[-1].message if alerts else ""

        comeback_p  = self.comeback.predict(s_dict)
        pace_res    = self.pace.predict(s_dict, self.state_history[:-1])
        clutch_st   = self.clutch.detect(s_dict, self.state_history[:-1])
        total_res   = self.total.predict(s_dict, self.state_history[:-1])
        rev_prob    = self.reversal.predict(s_dict, self.state_history[:-1])
        script_res  = self.script.predict(s_dict, self.state_history[:-1])
        value_res   = self.value.detect(ensemble_prob, self.live_odds)

        return EnsembleSnapshot(
            timestamp=time.time(),
            game_state=s_dict,
            ensemble_home_win_prob=ensemble_prob,
            ensemble_confidence=ens_conf,
            ci_lower=ci_lower,
            ci_upper=ci_upper,
            votes=live_votes,
            vote_agreement=vote_agreement,
            vote_disagreement_flags=disagreement_flags,
            comeback_prob=comeback_p,
            pace=pace_res["pace"],
            is_clutch=clutch_st.is_clutch,
            clutch_intensity=clutch_st.intensity,
            live_spread=self.spread.calculate(s_dict, momentum_score, pace_res.get("projected_total", 220)),
            projected_total=total_res["projected_total"],
            over_prob=total_res["over_prob"],
            momentum_reversal=rev_prob,
            game_script=script_res["script"],
            value_bet=asdict(value_res),
            top_alert=top_alert,
            proj_home=proj_home,
            proj_away=proj_away,
        )

    # ---------------------------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------------------------

    def _update_history(self, state: GameState, s_dict: dict):
        if self.state_history:
            last = self.state_history[-1]
            pts = max(
                state.home_score - last.get("home_score", 0),
                state.away_score - last.get("away_score", 0),
            )
            s_dict["pts_scored_this_poss"] = max(0, pts)
            s_dict["possession_count"] = last.get("possession_count", 0) + (
                1 if state.possession != last.get("possession") else 0
            )
        else:
            s_dict["pts_scored_this_poss"] = 0
            s_dict["possession_count"] = 1

        self.state_history.append(s_dict)
        if len(self.state_history) > 500:
            self.state_history.pop(0)

    def get_pregame_summary(self) -> dict:
        """Return pre-game vote summary for scouting report consumption."""
        votes = _compute_effective_weights(list(self._static_votes))
        ens = sum(v.home_win_prob * v.weight_effective for v in votes)
        agreement = sum(
            1 for v in votes if abs(v.home_win_prob - ens) <= DISAGREEMENT_THRESHOLD
        ) / max(1, len(votes))
        return {
            "home_team": self.home_team,
            "away_team": self.away_team,
            "pregame_ensemble": round(ens, 4),
            "vote_agreement": round(agreement, 3),
            "votes": [
                {
                    "model": v.model,
                    "home_win_prob": v.home_win_prob,
                    "confidence": v.confidence,
                    "weight_effective": v.weight_effective,
                }
                for v in votes
            ],
        }
