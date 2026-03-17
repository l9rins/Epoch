import numpy as np
import json
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from collections import defaultdict

# Feature dimension constant
FEATURE_DIM = 50
HOME_COURT_ADVANTAGE_PRIOR = 0.035

# Feature index map for interpretability
FEATURE_NAMES = [
    # Group A: Team Quality
    "home_ortg_norm", "away_ortg_norm", "home_drtg_norm", "away_drtg_norm",
    "home_net_rtg", "away_net_rtg", "home_win_pct", "away_win_pct",
    # Group B: Schedule and Fatigue
    "home_rest_norm", "away_rest_norm", "home_is_b2b", "away_is_b2b",
    "home_road_trip_norm", "away_road_trip_norm",
    "home_last5_winrate", "away_last5_winrate",
    "home_games_played_norm", "away_games_played_norm",
    # Group C: Venue and Context
    "altitude_diff_norm", "is_high_altitude",
    "home_court_advantage", "pace_diff_norm",
    "is_playoff", "game_number_norm",
    # Group D: Recent Form
    "home_momentum_3g", "away_momentum_3g",
    "home_momentum_10g", "away_momentum_10g",
    "home_ortg_trend", "away_ortg_trend",
    "home_drtg_trend", "away_drtg_trend",
    # Group E: Matchup
    "ortg_matchup_edge", "drtg_matchup_edge",
    "pace_compatibility", "h2h_win_rate_home",
    "home_sos_norm", "away_sos_norm",
    # Group F: Causal
    "causal_wp_adj", "injury_impact_home",
    "injury_impact_away", "referee_foul_rate_norm",
    # Group G: Advanced (Added in upgrade_ensemble)
    "elo_diff_norm", "home_elo_wp", "home_srs_norm", "away_srs_norm",
    "srs_diff_norm", "home_streak", "away_streak", "season_progress",
]

assert len(FEATURE_NAMES) == FEATURE_DIM, f"Expected {FEATURE_DIM} features, got {len(FEATURE_NAMES)}"

def _safe_div(a: float, b: float, default: float = 0.0) -> float:
    return a / b if b != 0 else default

def compute_momentum(
    team_games: List[dict],
    team: str,
    before_date: str,
    window: int = 5,
) -> float:
    """Win rate in last N games before date."""
    prior = sorted([
        g for g in team_games
        if (g.get("home_team") == team or g.get("away_team") == team)
        and g.get("game_date", "") < before_date
    ], key=lambda x: x.get("game_date", ""))[-window:]

    if not prior:
        return 0.5

    wins = 0
    for g in prior:
        if g.get("home_team") == team and g.get("home_win") == 1:
            wins += 1
        elif g.get("away_team") == team and g.get("home_win") == 0:
            wins += 1
    return wins / len(prior)

def compute_rating_trend(
    team_games: List[dict],
    team: str,
    before_date: str,
    rating_key_home: str,
    rating_key_away: str,
    window: int = 5,
) -> float:
    """
    Rating trend: (recent N-game avg) - (season avg) ÷ 10
    Positive = improving. Negative = declining.
    """
    all_prior = [
        g for g in team_games
        if (g.get("home_team") == team or g.get("away_team") == team)
        and g.get("game_date", "") < before_date
    ]
    if len(all_prior) < 2:
        return 0.0

    def get_rating(g):
        if g.get("home_team") == team:
            return g.get(rating_key_home, 110.0)
        return g.get(rating_key_away, 110.0)

    recent = [get_rating(g) for g in all_prior[-window:]]
    season = [get_rating(g) for g in all_prior]
    return _safe_div(np.mean(recent) - np.mean(season), 10.0)

def compute_h2h_win_rate(
    team_games: List[dict],
    home_team: str,
    away_team: str,
    before_date: str,
    season: str,
) -> float:
    """Home team win rate in head-to-head matchups this season."""
    h2h = [
        g for g in team_games
        if g.get("season") == season
        and g.get("game_date", "") < before_date
        and (
            (g.get("home_team") == home_team and g.get("away_team") == away_team) or
            (g.get("home_team") == away_team and g.get("away_team") == home_team)
        )
    ]
    if not h2h:
        return 0.5

    home_wins = sum(
        1 for g in h2h
        if g.get("home_team") == home_team and g.get("home_win") == 1
    )
    return _safe_div(home_wins, len(h2h), 0.5)

def engineer_features(
    game_log: dict,
    all_game_logs: List[dict],
    causal_wp_adjustment: float = 0.0,
    injury_impact_home: float = 0.0,
    injury_impact_away: float = 0.0,
    referee_foul_rate: float = 1.0,
    # New optional context for 50-feature vector
    elo_data: Optional[dict] = None,
    srs_data: Optional[dict] = None,
    team_histories: Optional[dict] = None,
) -> np.ndarray:
    """
    Transform one game log record into a 50-feature vector.
    all_game_logs required for momentum, trend, and H2H computation.
    """
    vec = np.zeros(FEATURE_DIM, dtype=np.float32)

    home = game_log.get("home_team", "")
    away = game_log.get("away_team", "")
    date = game_log.get("game_date", "")
    season = game_log.get("season", "")

    # Group A: Team Quality
    vec[0] = game_log.get("home_ortg", 110.0) / 120.0
    vec[1] = game_log.get("away_ortg", 110.0) / 120.0
    vec[2] = game_log.get("home_drtg", 110.0) / 120.0
    vec[3] = game_log.get("away_drtg", 110.0) / 120.0
    vec[4] = (game_log.get("home_ortg", 110.0) - game_log.get("home_drtg", 110.0)) / 20.0
    vec[5] = (game_log.get("away_ortg", 110.0) - game_log.get("away_drtg", 110.0)) / 20.0
    vec[6] = game_log.get("home_win_pct_prior", 0.5)
    vec[7] = game_log.get("away_win_pct_prior", 0.5)

    # Group B: Schedule and Fatigue
    vec[8] = min(game_log.get("home_rest_days", 2), 7) / 7.0
    vec[9] = min(game_log.get("away_rest_days", 2), 7) / 7.0
    vec[10] = float(game_log.get("home_is_b2b", False))
    vec[11] = float(game_log.get("away_is_b2b", False))
    vec[12] = min(game_log.get("home_road_trip_game", 0), 10) / 10.0
    vec[13] = min(game_log.get("away_road_trip_game", 0), 10) / 10.0
    vec[14] = game_log.get("home_last_5_wins", 2) / 5.0
    vec[15] = game_log.get("away_last_5_wins", 2) / 5.0
    vec[16] = 0.5   # games_played placeholder (requires season context)
    vec[17] = 0.5

    # Group C: Venue and Context
    home_alt = game_log.get("home_altitude_ft", 500)
    away_alt = game_log.get("away_altitude_ft", 500)
    alt_diff = (home_alt - away_alt) / 5280.0
    vec[18] = np.clip(alt_diff, -1.0, 1.0)
    vec[19] = float(abs(home_alt - away_alt) > 3000)
    vec[20] = HOME_COURT_ADVANTAGE_PRIOR
    vec[21] = (game_log.get("home_pace", 98.0) - game_log.get("away_pace", 98.0)) / 10.0
    vec[22] = 0.0   # is_playoff (not in regular season logs)
    vec[23] = 0.5   # game_number_in_season placeholder

    # Group D: Recent Form (requires historical game logs)
    if all_game_logs:
        vec[24] = compute_momentum(all_game_logs, home, date, window=3)
        vec[25] = compute_momentum(all_game_logs, away, date, window=3)
        vec[26] = compute_momentum(all_game_logs, home, date, window=10)
        vec[27] = compute_momentum(all_game_logs, away, date, window=10)
        vec[28] = compute_rating_trend(all_game_logs, home, date, "home_ortg", "away_ortg")
        vec[29] = compute_rating_trend(all_game_logs, away, date, "home_ortg", "away_ortg")
        vec[30] = compute_rating_trend(all_game_logs, home, date, "home_drtg", "away_drtg")
        vec[31] = compute_rating_trend(all_game_logs, away, date, "home_drtg", "away_drtg")
    else:
        vec[24:32] = 0.5

    # Group E: Matchup
    vec[32] = (game_log.get("home_ortg", 110.0) - game_log.get("away_drtg", 110.0)) / 20.0
    vec[33] = (game_log.get("away_ortg", 110.0) - game_log.get("home_drtg", 110.0)) / 20.0
    vec[34] = abs(game_log.get("home_pace", 98.0) - game_log.get("away_pace", 98.0)) / 10.0
    vec[35] = (
        compute_h2h_win_rate(all_game_logs, home, away, date, season)
        if all_game_logs else 0.5
    )
    vec[36] = 0.5   # sos placeholders
    vec[37] = 0.5

    # Group F: Causal
    vec[38] = causal_wp_adjustment
    vec[39] = injury_impact_home
    vec[40] = injury_impact_away
    vec[41] = np.clip(referee_foul_rate, 0.8, 1.2)

    # Group G: Advanced (indices 42-49)
    if elo_data and srs_data:
        gid = game_log.get("game_id", "")
        elo = elo_data.get(gid, {})
        srs = srs_data.get(gid, {})
        
        vec[42] = elo.get("elo_diff", 0.0) / 400.0
        vec[43] = elo.get("home_elo_wp", 0.574)
        vec[44] = srs.get("home_srs", 0.0) / 20.0
        vec[45] = srs.get("away_srs", 0.0) / 20.0
        vec[46] = (srs.get("home_srs", 0.0) - srs.get("away_srs", 0.0)) / 20.0
        
        # Streak and Season Progress
        if team_histories:
            home = game_log.get("home_team", "")
            away = game_log.get("away_team", "")
            date = game_log.get("game_date", "")
            season = game_log.get("season", "")
            
            vec[47] = compute_streak(team_histories.get(home, []), before_date=date)
            vec[48] = compute_streak(team_histories.get(away, []), before_date=date)
            vec[49] = compute_season_progress(date, season)
            
            vec[47] = compute_streak(team_histories.get(home, []), date)
            vec[48] = compute_streak(team_histories.get(away, []), date)
            vec[49] = compute_season_progress(date, season)
    else:
        # Fallback to defaults for Group G
        vec[42:50] = 0.0
        vec[43] = 0.574 # league avg home win rate
        vec[49] = 0.5   # mid season

    return vec


def compute_streak(team_games: list[dict], before_date: str, max_streak: int = 10) -> float:
    """
    Current win/loss streak for a team before a given date.
    Returns value in [-1, 1]: +1 = 10-game win streak, -1 = 10-game loss streak.
    """
    prior = [g for g in team_games if g.get("game_date", "") < before_date]
    if not prior:
        return 0.0

    streak = 0
    last_result = None

    for game in reversed(prior):
        is_home = game.get("home_team") == game.get("team_of_interest")
        home_win = game.get("home_win", 0)
        won = (is_home and home_win == 1) or (not is_home and home_win == 0)

        if last_result is None:
            last_result = won
            streak = 1
        elif won == last_result:
            streak += 1
        else:
            break

    signed_streak = streak if last_result else -streak
    return float(np.clip(signed_streak / max_streak, -1.0, 1.0))


def compute_season_progress(game_date: str, season: str) -> float:
    """
    Fraction of NBA regular season elapsed at game_date.
    Season typically runs October through April (~172 days).
    """
    try:
        season_year = int(season[:4])
        # Regular season: ~Oct 18 to Apr 10
        season_start = datetime(season_year, 10, 18)
        season_end = datetime(season_year + 1, 4, 10)
        game_dt = datetime.strptime(game_date, "%Y-%m-%d")
        progress = (game_dt - season_start).days / (season_end - season_start).days
        return float(np.clip(progress, 0.0, 1.0))
    except Exception:
        return 0.5

def build_feature_matrix(
    game_logs: List[dict],
    causal_adjustments: Optional[Dict[str, float]] = None,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Build X (feature matrix) and y (labels) from game logs.
    Returns X shape (N, 42) and y shape (N,).
    """
    causal_adjustments = causal_adjustments or {}
    X_rows = []
    y_rows = []

    for log in game_logs:
        game_id = log.get("game_id", "")
        causal_adj = causal_adjustments.get(game_id, 0.0)
        vec = engineer_features(log, game_logs, causal_wp_adjustment=causal_adj)
        X_rows.append(vec)
        y_rows.append(float(log.get("home_win", 0)))

    if not X_rows:
        return np.zeros((0, FEATURE_DIM), dtype=np.float32), np.zeros(0)

    return np.stack(X_rows).astype(np.float32), np.array(y_rows, dtype=np.float32)
