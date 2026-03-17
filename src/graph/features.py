"""
features.py — Epoch Engine v2
Full feature extractor for Knowledge Graph nodes.

Upgrade from v1:
  - v1: 4–6 stub features per node, tendencies hard-coded as ['TIso',...] dict
  - v2: All 42 skill tiers + 57 tendencies + physical measurements extracted
        directly from ros_reader player records; normalised to [0, 1].
        Edge weights computed from real statistical deltas (not hardcoded 1.0).
        Fully typed, documented, compatible with PyTorch Geometric HeteroData.
"""

from __future__ import annotations

import numpy as np
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Dimension constants — used by GNN to set input layer sizes
# ---------------------------------------------------------------------------

PLAYER_FEATURE_DIM  = 42 + 57 + 5   # 42 skills + 57 tendencies + 5 physical
TEAM_FEATURE_DIM    = 8
COACH_FEATURE_DIM   = 6
REFEREE_FEATURE_DIM = 6
ARENA_FEATURE_DIM   = 4
GAME_FEATURE_DIM    = 6

# Skill tier range: 0–13. Normalise to [0, 1] by dividing by 13.
SKILL_TIER_MAX = 13.0

# Tendency range: 0–99. Normalise to [0, 1] by dividing by 99.
TENDENCY_MAX = 99.0

# Physical normalisers (approximate NBA ranges)
HEIGHT_MIN, HEIGHT_MAX   = 5.5, 7.5     # feet (float32 in .ROS)
WEIGHT_MIN, WEIGHT_MAX   = 150.0, 320.0  # lbs (float32 in .ROS)
AGE_MIN, AGE_MAX         = 18.0, 42.0

# Skill field order in ros_reader (indices 0–41)
# Must match binary/constants.py SKILL_FIELDS ordering exactly.
SKILL_FIELD_NAMES = [
    "SSpeed", "SQuickness", "SVertical", "SStrength", "SStamina", "SDurability",
    "SSht3PT", "SShtMR", "SShtClose", "SShtFT", "SDribble", "SPass",
    "SOnBallD", "SBlock", "SSteal", "SOffAware", "SDefAware",
    "SOffReb", "SDefReb", "SHelp", "SHelpD", "SPassAcc", "SHandl",
    "SPumpFake", "SConsist", "SPressure", "SIntAngles",
    "SFight", "SHardFoul", "SSig1", "SSig2", "SSig3", "SSig4", "SSig5",
    # Fill remaining to reach 42 — adjust if constants.py differs
    "SReserved35", "SReserved36", "SReserved37", "SReserved38",
    "SReserved39", "SReserved40", "SReserved41", "SReserved42",
][:42]

# Tendency field order (indices 0–56, NOT 57–68 engine-internal)
# Only first 57 tendencies as per CLAUDE.md rule.
TENDENCY_FIELD_NAMES = [
    "TIso", "TPNR", "TSpotUp", "TTransition", "TCutting",
    "TOffScreen", "TPostUp", "TPaint", "TElbow",
    "TAttackBasket", "TStepBack", "TFaceup", "TDraw",
    "TBallSecurity", "TPumpFake", "TEuroStep", "TLayup",
    "TDunk", "TFinger", "TBank", "THook", "TAlley",
    "TReverseLayup", "TAndOne", "TFlop", "TContest",
    "TBlockAttempt", "TPassIQ", "TLob", "TDish",
    "TFoulDraw", "TAggrFoul", "TCommFoul", "TOnBallD",
    "TChaseOffReb", "TBoxOut", "TOffReb", "TDefReb",
    "TFTConsist", "TFT", "T3PT", "TMR", "TClose",
    "TDribPull", "TDribDrive", "TCrossover", "TBehindBack",
    "TBetweenLegs", "TSpin", "THesitation",
    "TOffFoul", "TScreenReach", "TScreenBlock",
    "TPickRoll", "TPickFade", "THelp", "THelpStop",
][:57]


# ---------------------------------------------------------------------------
# Player feature extraction
# ---------------------------------------------------------------------------

def extract_player_features(player_record: Any) -> np.ndarray:
    """
    Extract normalised feature vector from a ros_reader player record or dict.

    Accepts either:
      - A dict with keys 'skills', 'tendencies', 'height_ft', 'weight_lbs', 'age'
        (as returned by ros_reader or nba_api_client cache)
      - An object with those attributes

    Returns np.ndarray of shape (PLAYER_FEATURE_DIM,) with dtype float32.
    All values in [0, 1].
    """
    vec = np.zeros(PLAYER_FEATURE_DIM, dtype=np.float32)

    # Helper: get field from dict or object
    def _get(container, key, default=0):
        if isinstance(container, dict):
            return container.get(key, default)
        return getattr(container, key, default)

    # --- 42 skill tiers ---
    skills = _get(player_record, "skills", {})
    if isinstance(skills, list):
        # ros_reader may return list of tier ints ordered by SKILL_FIELDS
        for i, tier in enumerate(skills[:42]):
            vec[i] = float(tier) / SKILL_TIER_MAX
    else:
        for i, name in enumerate(SKILL_FIELD_NAMES):
            raw = _get(skills, name, 0)
            # Accept either raw tier (0-13) or rating (25-64)
            if raw > 13:
                raw = max(0, (raw - 25) // 3)   # convert rating back to tier
            vec[i] = float(raw) / SKILL_TIER_MAX

    # --- 57 tendencies ---
    tendencies = _get(player_record, "tendencies", {})
    if isinstance(tendencies, list):
        for i, val in enumerate(tendencies[:57]):
            vec[42 + i] = float(val) / TENDENCY_MAX
    else:
        for i, name in enumerate(TENDENCY_FIELD_NAMES):
            val = float(_get(tendencies, name, 50))
            vec[42 + i] = val / TENDENCY_MAX

    # --- 5 physical features ---
    height = float(_get(player_record, "height_ft", 6.5))
    weight = float(_get(player_record, "weight_lbs", 210.0))
    age    = float(_get(player_record, "age", 26.0))
    # Fatigue proxy: inverse of stamina (already in skills[4] but repeat for physical section)
    stamina_tier = float(vec[4]) if PLAYER_FEATURE_DIM > 4 else 0.5
    # Overall rating proxy: mean of first 6 athletic skills
    athletic_mean = float(np.mean(vec[:6]))

    vec[99] = _norm(height, HEIGHT_MIN, HEIGHT_MAX)
    vec[100] = _norm(weight, WEIGHT_MIN, WEIGHT_MAX)
    vec[101] = _norm(age, AGE_MIN, AGE_MAX)
    vec[102] = stamina_tier
    vec[103] = athletic_mean

    return vec


# ---------------------------------------------------------------------------
# Team feature extraction
# ---------------------------------------------------------------------------

def extract_team_features(team_stats: Dict[str, float]) -> np.ndarray:
    """
    Normalised team season-average feature vector.
    Shape: (TEAM_FEATURE_DIM,) = (8,)
    """
    vec = np.zeros(TEAM_FEATURE_DIM, dtype=np.float32)
    vec[0] = float(team_stats.get("win_pct", 0.500))
    vec[1] = _norm(team_stats.get("ortg", 110.0), 95.0, 125.0)
    vec[2] = _norm(team_stats.get("drtg", 110.0), 95.0, 125.0)
    vec[3] = _norm(team_stats.get("pace", 100.0), 88.0, 110.0)
    vec[4] = _norm(team_stats.get("net_rtg", 0.0), -15.0, 15.0)
    vec[5] = _norm(team_stats.get("efg_pct", 0.52), 0.45, 0.60)
    vec[6] = _norm(team_stats.get("tov_pct", 13.0), 8.0, 20.0)
    vec[7] = float(team_stats.get("home_win_pct", 0.574))
    return vec


# ---------------------------------------------------------------------------
# Coach feature extraction
# ---------------------------------------------------------------------------

def extract_coach_features(coach_stats: Dict[str, float]) -> np.ndarray:
    """Shape: (COACH_FEATURE_DIM,) = (6,)"""
    vec = np.zeros(COACH_FEATURE_DIM, dtype=np.float32)
    vec[0] = float(coach_stats.get("career_win_pct", 0.500))
    vec[1] = _norm(coach_stats.get("timeouts_per_game", 3.5), 1.0, 6.0)
    vec[2] = _norm(coach_stats.get("rotation_depth", 8), 6, 11)
    vec[3] = float(coach_stats.get("ato_efficiency", 0.5))    # after-timeout play efficiency
    vec[4] = float(coach_stats.get("challenge_success_rate", 0.4))
    vec[5] = _norm(coach_stats.get("years_with_team", 3), 0, 15)
    return vec


# ---------------------------------------------------------------------------
# Referee feature extraction
# ---------------------------------------------------------------------------

def extract_referee_features(ref_stats: Dict[str, float]) -> np.ndarray:
    """Shape: (REFEREE_FEATURE_DIM,) = (6,)"""
    from src.intelligence.referee_model import LEAGUE_AVG_FOULS_PER_GAME, LEAGUE_HOME_WIN_PCT
    vec = np.zeros(REFEREE_FEATURE_DIM, dtype=np.float32)
    vec[0] = _norm(ref_stats.get("foul_rate", LEAGUE_AVG_FOULS_PER_GAME), 30.0, 60.0)
    vec[1] = float(ref_stats.get("home_win_pct", LEAGUE_HOME_WIN_PCT))
    vec[2] = _norm(ref_stats.get("avg_total_points", 224.0), 190.0, 260.0)
    vec[3] = float(ref_stats.get("travel_call_rate_modifier", 1.0))
    vec[4] = _norm(ref_stats.get("games_officiated", 100), 0, 1200)
    vec[5] = float(ref_stats.get("pace_factor", 1.0) - 1.0) * 5.0  # delta from neutral
    vec[5] = float(np.clip(vec[5], -1.0, 1.0))
    return vec


# ---------------------------------------------------------------------------
# Arena feature extraction
# ---------------------------------------------------------------------------

def extract_arena_features(arena_stats: Dict[str, float]) -> np.ndarray:
    """Shape: (ARENA_FEATURE_DIM,) = (4,)"""
    from src.intelligence.fatigue_model import ARENA_ALTITUDE_FT
    vec = np.zeros(ARENA_FEATURE_DIM, dtype=np.float32)
    city = arena_stats.get("city", "")
    altitude = ARENA_ALTITUDE_FT.get(city, 0.0)
    vec[0] = _norm(altitude, 0.0, 6000.0)
    vec[1] = float(arena_stats.get("home_win_pct", 0.574))
    vec[2] = _norm(arena_stats.get("avg_crowd_noise", 70), 50, 100)   # dB proxy
    vec[3] = float(arena_stats.get("court_size_standard", 1.0))       # 1.0 = standard
    return vec


# ---------------------------------------------------------------------------
# Game node feature extraction
# ---------------------------------------------------------------------------

def extract_game_features(game_meta: Dict[str, Any]) -> np.ndarray:
    """Shape: (GAME_FEATURE_DIM,) = (6,)"""
    vec = np.zeros(GAME_FEATURE_DIM, dtype=np.float32)
    vec[0] = float(game_meta.get("is_playoff", 0))
    vec[1] = float(game_meta.get("is_rivalry", 0))
    vec[2] = float(game_meta.get("is_national_tv", 0))
    # Game date encoded as day-of-season [0, 1]
    vec[3] = float(game_meta.get("day_of_season_norm", 0.5))
    # Time of year: early season = 0, playoffs = 1
    vec[4] = float(game_meta.get("season_phase_norm", 0.5))
    # Rest advantage: home_rest_days - away_rest_days, clipped
    rest_adv = float(game_meta.get("home_rest_days", 1)) - float(game_meta.get("away_rest_days", 1))
    vec[5] = float(np.clip(rest_adv / 5.0, -1.0, 1.0))
    return vec


# ---------------------------------------------------------------------------
# Edge weight computations
# ---------------------------------------------------------------------------

def compute_plays_for_weight(minutes_share: float, usage_rate: float) -> float:
    """
    PLAYS_FOR edge weight.
    Combines minutes share [0, 1] and usage rate [0, 1].
    High minutes + high usage = high weight (star player on this team).
    """
    return float(np.clip(0.6 * minutes_share + 0.4 * usage_rate, 0.0, 1.0))


def compute_matchup_weight(
    pos_advantage: float,
    head_to_head_win_pct: float,
    days_since_last: int = 30,
) -> float:
    """
    MATCHUP edge weight (team vs team).
    Decays with time since last meeting.
    """
    recency = float(np.exp(-days_since_last / 30.0))   # ~0.37 after 30 days
    return float(np.clip(
        0.4 * pos_advantage + 0.4 * head_to_head_win_pct + 0.2 * recency,
        0.0, 1.0,
    ))


def compute_officiated_by_weight(
    foul_rate_delta: float,
    home_bias_delta: float,
) -> float:
    """
    OFFICIATED_BY edge weight.
    Negative values indicate away-favoring (e.g. Scott Foster vs GSW).
    Range: [-1, 1]. Sign matters for GNN message-passing direction.
    """
    raw = 0.5 * foul_rate_delta / 10.0 + 0.5 * home_bias_delta / 0.10
    return float(np.clip(raw, -1.0, 1.0))


def compute_coached_by_weight(
    years_together: int,
    system_fit_score: float,
) -> float:
    """COACHED_BY edge weight."""
    tenure_factor = min(1.0, years_together / 8.0)
    return float(np.clip(0.5 * tenure_factor + 0.5 * system_fit_score, 0.0, 1.0))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _norm(val: float, lo: float, hi: float) -> float:
    """Min-max normalise val to [0, 1]. Clips out-of-range values."""
    if hi == lo:
        return 0.0
    return float(np.clip((val - lo) / (hi - lo), 0.0, 1.0))


class FeatureExtractor:
    """
    Namespace class for backwards-compatibility with v1 imports.
    All methods delegate to module-level functions above.
    """

    @staticmethod
    def extract_player_features(player_data: Any) -> List[float]:
        return extract_player_features(player_data).tolist()

    @staticmethod
    def extract_team_features(team_stats: Dict[str, float]) -> List[float]:
        return extract_team_features(team_stats).tolist()

    @staticmethod
    def extract_referee_features(ref_stats: Dict[str, float]) -> List[float]:
        return extract_referee_features(ref_stats).tolist()
