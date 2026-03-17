"""
win_probability.py — Epoch Engine v2
Live win probability model with 30-feature vector.

Upgrade from v1:
  - v1: 14 features, no possession context, no leverage index, pure RF fallback
  - v2: 30 features across 5 groups:
        Group 1 — Game state (6)       score diff, time, quarter, clock, OT flag
        Group 2 — Pace / efficiency (6) pts-per-possession, TS%, poss/min both teams
        Group 3 — Leverage (4)         leverage index, "come-back difficulty", clutch flag
        Group 4 — Momentum (4)         rolling momentum, scoring run length, reversal prob
        Group 5 — Context (10)         fatigue home/away, spacing, paint density, 3PT cvg,
                                        pick-roll, fast break, open shooter, ref pace factor,
                                        altitude delta

        Survival correction: Beta prior hard-clips impossible probabilities at
        extreme score differentials (prevents RF from predicting 0.5 at -30 with 5s left).

        NBA tracking API inputs: defensive_spacing, paint_density, three_point_coverage,
        pace_home, pace_away — wired from nba_api PlayerTrackingShooting / SynergyPlayType.
        These replace the OpenCV vision module inputs when live video is unavailable.
"""

from __future__ import annotations

import math
import json
import joblib
import numpy as np
from pathlib import Path
from datetime import datetime
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split

try:
    from src.simulation.memory_reader import GameState
except ImportError:
    class GameState:  # type: ignore
        def __init__(self, **kw):
            for k, v in kw.items(): setattr(self, k, v)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MODEL_PATH       = Path("data/models/win_prob_rf.pkl")
TRAIN_DATA       = Path("data/synthetic/games_10k.jsonl")
FEATURE_DIM      = 30

# RF config
RF_N_ESTIMATORS  = 200
RF_MAX_DEPTH     = 25

# Survival model: at |score_diff| >= this, clip probability aggressively
SURVIVAL_CLIP_DIFF   = 25.0
SURVIVAL_TIME_CUTOFF = 120.0   # seconds remaining — below this, survival kicks in

# Leverage index calibration: how much the next possession matters
# WP swings more per possession as time decreases
LEVERAGE_TIME_SCALE = 300.0   # ~1 quarter

# Feature names — used by ensemble_model.py for importance reporting
FEATURE_NAMES = [
    # Group 1: Game state
    "score_diff", "time_remaining", "quarter", "clock_pct", "is_overtime",
    "abs_score_diff",
    # Group 2: Pace / efficiency
    "home_pts_per_poss", "away_pts_per_poss", "home_pace_poss_min", "away_pace_poss_min",
    "pts_diff_rate", "efficiency_gap",
    # Group 3: Leverage
    "leverage_index", "comeback_difficulty", "is_clutch_situation", "win_prob_volatility",
    # Group 4: Momentum
    "momentum", "scoring_run_home", "scoring_run_away", "momentum_delta",
    # Group 5: Context
    "defensive_spacing", "paint_density", "three_point_coverage",
    "pick_roll_active", "fast_break_active", "open_shooter_active",
    "fatigue_home", "fatigue_away",
    "ref_pace_factor", "altitude_delta_norm",
]

assert len(FEATURE_NAMES) == FEATURE_DIM, f"Feature name count {len(FEATURE_NAMES)} != {FEATURE_DIM}"


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------

class WinProbabilityModel:
    MODEL_PATH = MODEL_PATH
    TRAIN_DATA = TRAIN_DATA

    def __init__(self):
        self.rf_model = None
        self._load_model()
        # Momentum delta tracking
        self._last_momentum: float = 0.0
        self._last_win_prob: float = 0.5

    def _load_model(self):
        if self.MODEL_PATH.exists():
            try:
                self.rf_model = joblib.load(self.MODEL_PATH)
            except Exception as e:
                print(f"WinProbabilityModel: error loading model — {e}")

    # ---------------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------------

    def __call__(
        self,
        state: GameState,
        momentum: float = 0.0,
        extra_features: dict | None = None,
    ) -> float:
        """
        Compute live win probability for home team.
        Returns float in [0.05, 0.95].
        """
        feats = self._extract_features(state, momentum, extra_features)

        if self.rf_model is not None:
            try:
                prob = float(self.rf_model.predict_proba(np.array([feats]))[0][1])
            except Exception:
                prob = self._logistic_fallback(state)
        else:
            prob = self._logistic_fallback(state)

        # Apply survival correction at extreme game states
        prob = self._survival_correction(prob, state)

        prob = round(max(0.05, min(0.95, prob)), 4)
        self._last_win_prob = prob
        return prob

    def projected_score(self, state: GameState) -> tuple[int, int]:
        """Simple pace-based score projection."""
        time_elapsed   = self.calculate_time_elapsed(state)
        time_remaining = self.calculate_time_remaining(state)
        if time_elapsed <= 0:
            return state.home_score, state.away_score
        home_rate = state.home_score / time_elapsed
        away_rate = state.away_score / time_elapsed
        return (
            int(state.home_score + home_rate * time_remaining),
            int(state.away_score + away_rate * time_remaining),
        )

    # ---------------------------------------------------------------------------
    # Feature extraction (30 features)
    # ---------------------------------------------------------------------------

    def _extract_features(
        self,
        state: GameState,
        momentum: float = 0.0,
        extra: dict | None = None,
    ) -> list[float]:
        extra = extra or {}

        time_rem  = self.calculate_time_remaining(state)
        time_elap = self.calculate_time_elapsed(state)
        score_diff = state.home_score - state.away_score
        q = state.quarter

        # Pace estimates
        poss_count = max(1, extra.get("possession_count", max(1, int(time_elap / 24.0))))
        home_pts_per_poss = state.home_score / poss_count
        away_pts_per_poss = state.away_score / poss_count
        home_pace_poss_min =充分の / max(1, time_elap / 60.0)
        away_pace_poss_min = home_pace_poss_min   # approximate — improve with real possession tracking
        pts_diff_rate = (state.home_score - state.away_score) / max(1, time_elap) * 60
        efficiency_gap = home_pts_per_poss - away_pts_per_poss

        # Leverage index
        leverage = self._leverage_index(score_diff, time_rem)
        comeback_diff = self._comeback_difficulty(score_diff, time_rem)
        is_clutch = float(abs(score_diff) <= 5 and time_rem <= 300)
        # WP volatility proxy: how much WP can swing in one possession
        wp_volatility = min(1.0, leverage / 5.0)

        # Momentum features
        momentum_delta = momentum - self._last_momentum
        scoring_run_home = float(extra.get("home_scoring_run", 0))
        scoring_run_away = float(extra.get("away_scoring_run", 0))
        self._last_momentum = momentum

        # Context features (NBA tracking API / vision / fatigue / referee)
        defensive_spacing    = float(extra.get("defensive_spacing", 50.0))
        paint_density        = float(extra.get("paint_density", 5.0))
        three_pt_coverage    = float(extra.get("three_point_coverage", 50.0))
        pick_roll            = float(extra.get("pick_roll", 0))
        fast_break           = float(extra.get("fast_break", 0))
        open_shooter         = float(extra.get("open_shooter", 0))
        fatigue_home         = float(extra.get("fatigue_home", 1.0))
        fatigue_away         = float(extra.get("fatigue_away", 1.0))
        ref_pace_factor      = float(extra.get("ref_pace_factor", 1.0))
        altitude_delta_norm  = float(extra.get("altitude_delta_norm", 0.0))

        return [
            # Group 1: Game state
            float(score_diff),
            float(time_rem),
            float(q),
            float(state.clock / 720.0),          # clock as pct of quarter
            float(q > 4),                         # OT flag
            float(abs(score_diff)),
            # Group 2: Pace / efficiency
            home_pts_per_poss,
            away_pts_per_poss,
            home_pace_poss_min,
            away_pace_poss_min,
            pts_diff_rate,
            efficiency_gap,
            # Group 3: Leverage
            leverage,
            comeback_diff,
            is_clutch,
            wp_volatility,
            # Group 4: Momentum
            float(momentum),
            scoring_run_home,
            scoring_run_away,
            momentum_delta,
            # Group 5: Context
            defensive_spacing / 100.0,
            paint_density / 10.0,
            three_pt_coverage / 100.0,
            pick_roll,
            fast_break,
            open_shooter,
            fatigue_home,
            fatigue_away,
            ref_pace_factor,
            altitude_delta_norm,
        ]

    # ---------------------------------------------------------------------------
    # Time helpers
    # ---------------------------------------------------------------------------

    def calculate_time_remaining(self, state: GameState) -> float:
        q = state.quarter if state.quarter <= 4 else 4
        return max(0.0, ((4 - q) * 720) + state.clock)

    def calculate_time_elapsed(self, state: GameState) -> float:
        return (4 * 720) - self.calculate_time_remaining(state)

    # ---------------------------------------------------------------------------
    # Fallback / corrections
    # ---------------------------------------------------------------------------

    def _logistic_fallback(self, state: GameState) -> float:
        """v1-compatible logistic fallback when RF model not available."""
        time_remaining = self.calculate_time_remaining(state)
        score_diff = state.home_score - state.away_score
        scaling_factor = 1.0 / (math.sqrt(max(time_remaining / 60, 0.01)) + 1.0)
        z = score_diff * 0.5 * scaling_factor
        return 1 / (1 + math.exp(-z))

    def _leverage_index(self, score_diff: float, time_rem: float) -> float:
        """
        How much does the next possession matter?
        Inspired by baseball LI: high when game is close, late.
        """
        if time_rem <= 0:
            return 0.0
        closeness = max(0.0, 1.0 - abs(score_diff) / 20.0)
        urgency   = math.exp(-time_rem / LEVERAGE_TIME_SCALE)
        return round(min(5.0, closeness * urgency * 5.0), 3)

    def _comeback_difficulty(self, score_diff: float, time_rem: float) -> float:
        """
        How hard is it for the trailing team to come back?
        Returns [0, 1] where 1 = near impossible.
        """
        if time_rem <= 0 or score_diff == 0:
            return float(score_diff != 0)
        pts_per_sec = 0.04    # approx NBA scoring rate
        pts_available = time_rem * pts_per_sec
        needed = abs(score_diff)
        return min(1.0, needed / max(pts_available, 1.0))

    def _survival_correction(self, prob: float, state: GameState) -> float:
        """
        At extreme score differentials with little time, the RF can still output
        near-0.5 on unseen data. Apply a Beta prior that hard-clips these.
        """
        time_rem   = self.calculate_time_remaining(state)
        score_diff = state.home_score - state.away_score

        if time_rem > SURVIVAL_TIME_CUTOFF or abs(score_diff) < SURVIVAL_CLIP_DIFF:
            return prob

        # Beta(α, β) where α/β encodes direction and certainty
        # At -30 with 60s left: P(home wins) should be ~0.03 max
        certainty = min(0.97, abs(score_diff) / 40.0)
        if score_diff < 0:
            # Home is trailing: clip max probability
            return min(prob, 1.0 - certainty)
        else:
            # Home is leading: clip min probability
            return max(prob, certainty)

    # ---------------------------------------------------------------------------
    # Training
    # ---------------------------------------------------------------------------

    def train_on_instance(self, games: list | None = None):
        self.train(games)
        self._load_model()

    @classmethod
    def train(cls, games: list | None = None):
        X, y = [], []
        model_inst = cls.__new__(cls)
        model_inst._last_momentum = 0.0
        model_inst._last_win_prob = 0.5
        model_inst.rf_model = None

        class DummyState:
            def __init__(self, d):
                self.quarter    = d["quarter"]
                self.clock      = d["clock"]
                self.home_score = d["home_score"]
                self.away_score = d["away_score"]
                self.possession = d.get("possession", 0)

        if games is None:
            if not cls.TRAIN_DATA.exists():
                print(f"Training data not found: {cls.TRAIN_DATA}")
                return
            with open(cls.TRAIN_DATA) as f:
                games = [json.loads(line) for line in f]

        print(f"Training WinProbabilityModel v2 on {len(games)} games ({FEATURE_DIM} features)...")

        for game in games:
            home_won = 1 if game["final_home"] > game["final_away"] else 0
            for i, s in enumerate(game["states"]):
                if i % 10 != 0:
                    continue
                feat = model_inst._extract_features(DummyState(s), s.get("momentum", 0.0), s)
                X.append(feat)
                y.append(home_won)

        if not X:
            print("No training samples produced.")
            return

        X = np.array(X, dtype=np.float32)
        y = np.array(y, dtype=np.int8)
        X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.2, random_state=42)

        rf = RandomForestClassifier(
            n_estimators=RF_N_ESTIMATORS,
            max_depth=RF_MAX_DEPTH,
            n_jobs=-1,
            random_state=42,
        )
        rf.fit(X_train, y_train)

        from sklearn.metrics import roc_auc_score
        probs = rf.predict_proba(X_val)[:, 1]
        auc = float(roc_auc_score(y_val, probs))

        cls.MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(rf, cls.MODEL_PATH)

        meta = {"auc": auc, "feature_dim": FEATURE_DIM, "timestamp": str(datetime.now())}
        with open(cls.MODEL_PATH.parent / "win_prob_meta.json", "w") as f:
            json.dump(meta, f)

        print(f"WinProbabilityModel v2 saved (AUC: {auc:.3f}, features: {FEATURE_DIM})")
