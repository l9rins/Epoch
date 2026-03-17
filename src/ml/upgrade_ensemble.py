"""
upgrade_ensemble.py — Epoch Engine
=====================================
Three-part upgrade to push ensemble AUC from 0.628 toward the 0.68-0.72
realistic ceiling for pre-game NBA prediction:

  Part 1 — Elo + SRS feature computation (the biggest single lever)
  Part 2 — 5-season player log ingestion (more injury signal coverage)
  Part 3 — Expanded 50-feature vector + full retrain with honest AUC targets

AUC reality check (documented here permanently):
  Pre-game NBA prediction AUC ceiling with box-score features: ~0.68-0.72
  Academic benchmarks: FiveThirtyEight Elo alone ≈ 0.63, with features ≈ 0.69
  Our 0.870 target was inherited from synthetic data and is not achievable
  with pre-game features alone. The in-game model (0.969) is the right number
  to optimize — it has access to the score, which is almost everything.
  Pre-game ensemble goal: >= 0.680 AUC, Brier <= 0.230.

Usage:
    python -m src.ml.upgrade_ensemble                    # full pipeline
    python -m src.ml.upgrade_ensemble --elo-only         # just compute Elo
    python -m src.ml.upgrade_ensemble --no-player-logs   # skip player log fetch
    python -m src.ml.upgrade_ensemble --dry-run          # report only
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import time
import os
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
from src.ml.feature_engineer import engineer_features

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("upgrade_ensemble")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REAL_DATA_DIR = Path("data/real")
GAME_LOGS_PATH = Path("data/real_game_logs.jsonl")
PLAYER_LOGS_PATH = Path("data/player_game_logs.jsonl")
INJURY_LOGS_PATH = Path("data/injury_game_logs.jsonl")
ENRICHED_PATH = Path("data/enriched_game_logs.jsonl")
ELO_CACHE_PATH = Path("data/elo_ratings.json")
SRS_CACHE_PATH = Path("data/srs_ratings.json")
UPGRADED_OUTPUT = Path("data/upgraded_game_logs.jsonl")
REPORT_PATH = Path("data/upgrade_report.json")

SEASONS = ["2020-21", "2021-22", "2022-23", "2023-24", "2024-25"]

# ---------------------------------------------------------------------------
# Realistic AUC targets (replacing the unreachable 0.870)
# ---------------------------------------------------------------------------

PRE_GAME_AUC_TARGET = 0.680       # achievable with Elo + SRS + injury features
PRE_GAME_AUC_MINIMUM = 0.650      # below this = something is wrong with features
PRE_GAME_BRIER_TARGET = 0.230     # probability calibration target
IN_GAME_AUC_TARGET = 0.960        # already achieved (0.969)

# ---------------------------------------------------------------------------
# Part 1: Elo Rating System
# ---------------------------------------------------------------------------
#
# Standard NBA Elo implementation based on FiveThirtyEight methodology:
#   - K-factor = 20 (standard for NBA)
#   - Home court adjustment = +100 Elo points to home team
#   - Season carryover = 75% (25% regression to mean each season)
#   - Starting Elo = 1500 for all teams
#
# Elo differential is the single strongest pre-game predictor.
# A 100-point Elo gap = ~14% win probability difference.

ELO_K = 20.0
ELO_HOME_ADVANTAGE = 100.0
ELO_STARTING = 1500.0
ELO_SEASON_CARRYOVER = 0.75
ELO_SCALE = 400.0          # logistic scale factor (FiveThirtyEight standard)


def elo_expected(rating_a: float, rating_b: float) -> float:
    """Expected win probability for team A vs team B."""
    return 1.0 / (1.0 + 10.0 ** ((rating_b - rating_a) / ELO_SCALE))


def elo_update(
    rating_a: float,
    rating_b: float,
    score_a: int,
    score_b: int,
    is_a_home: bool = True,
) -> tuple[float, float]:
    """
    Update Elo ratings after a game.
    Applies home court adjustment before computing expected outcome.
    Returns (new_rating_a, new_rating_b).
    """
    home_adj = ELO_HOME_ADVANTAGE if is_a_home else -ELO_HOME_ADVANTAGE
    expected_a = elo_expected(rating_a + home_adj, rating_b)
    actual_a = 1.0 if score_a > score_b else 0.0

    # Margin of victory multiplier (FiveThirtyEight method)
    # Larger wins = larger Elo update, but with diminishing returns
    margin = abs(score_a - score_b)
    mov_mult = math.log(margin + 1) * (2.2 / ((abs(rating_a - rating_b) * 0.001) + 2.2))
    mov_mult = max(1.0, min(mov_mult, 2.5))  # cap between 1x and 2.5x

    delta = ELO_K * mov_mult * (actual_a - expected_a)
    return rating_a + delta, rating_b - delta


def compute_elo_ratings(games: list[dict]) -> dict[str, dict[str, float]]:
    """
    Compute pre-game Elo ratings for every game in the dataset.

    Returns {game_id: {"home_elo": float, "away_elo": float, "elo_diff": float}}
    where the Elo values represent ratings BEFORE the game was played.
    """
    # Sort all games chronologically
    sorted_games = sorted(games, key=lambda g: g.get("game_date", ""))

    # Initialize ratings
    team_elo: dict[str, float] = defaultdict(lambda: ELO_STARTING)
    current_season: str = ""
    elo_snapshot: dict[str, dict[str, float]] = {}

    for game in sorted_games:
        gid = game.get("game_id", "")
        home = game.get("home_team", "")
        away = game.get("away_team", "")
        home_score = int(game.get("home_score", game.get("final_home", 0)))
        away_score = int(game.get("away_score", game.get("final_away", 0)))
        season = game.get("season", "")

        # Season transition: regress 25% toward mean
        if season != current_season and current_season:
            log.debug("Season transition %s → %s, applying Elo regression", current_season, season)
            for team in list(team_elo.keys()):
                team_elo[team] = (
                    ELO_SEASON_CARRYOVER * team_elo[team]
                    + (1 - ELO_SEASON_CARRYOVER) * ELO_STARTING
                )
        current_season = season

        # Capture pre-game Elo (this is what we use as a feature)
        home_elo_pre = team_elo[home]
        away_elo_pre = team_elo[away]
        elo_diff = home_elo_pre - away_elo_pre

        elo_snapshot[gid] = {
            "home_elo": round(home_elo_pre, 1),
            "away_elo": round(away_elo_pre, 1),
            "elo_diff": round(elo_diff, 1),
            "home_elo_wp": round(elo_expected(
                home_elo_pre + ELO_HOME_ADVANTAGE, away_elo_pre
            ), 4),
        }

        # Update ratings after game (only if scores are valid)
        if home_score > 0 or away_score > 0:
            new_home, new_away = elo_update(
                home_elo_pre, away_elo_pre,
                home_score, away_score,
                is_a_home=True,
            )
            team_elo[home] = new_home
            team_elo[away] = new_away

    log.info("Elo computed for %d games across %d teams", len(elo_snapshot), len(team_elo))
    return elo_snapshot


# ---------------------------------------------------------------------------
# Part 1b: Simple Rating System (SRS)
# ---------------------------------------------------------------------------
#
# SRS = average point differential adjusted for strength of schedule.
# Computed iteratively (converges in ~10 passes).
# More stable than raw point differential for measuring team quality.

SRS_ITERATIONS = 20
SRS_CONVERGENCE_THRESHOLD = 0.001


def compute_srs_ratings(games: list[dict]) -> dict[str, dict[str, float]]:
    """
    Compute rolling SRS for each team at each game date.
    Returns {game_id: {"home_srs": float, "away_srs": float, "srs_diff": float}}

    Uses a simplified rolling SRS:
    - For each game, compute SRS from the last 20 games before that date
    - This gives us a pre-game SRS snapshot
    """
    sorted_games = sorted(games, key=lambda g: g.get("game_date", ""))
    srs_snapshot: dict[str, dict[str, float]] = {}

    # Build team game history
    team_game_history: dict[str, list[dict]] = defaultdict(list)
    for game in sorted_games:
        home = game.get("home_team", "")
        away = game.get("away_team", "")
        home_score = int(game.get("home_score", game.get("final_home", 0)))
        away_score = int(game.get("away_score", game.get("final_away", 0)))
        team_game_history[home].append({
            "opponent": away, "pts_for": home_score, "pts_against": away_score,
            "date": game.get("game_date", ""),
        })
        team_game_history[away].append({
            "opponent": home, "pts_for": away_score, "pts_against": home_score,
            "date": game.get("game_date", ""),
        })

    def _compute_srs_at_date(team: str, before_date: str, window: int = 20) -> float:
        """Simple iterative SRS for a team's recent games."""
        history = [
            g for g in team_game_history[team]
            if g["date"] < before_date
        ][-window:]

        if len(history) < 3:
            return 0.0

        # Point differential
        pd = np.mean([g["pts_for"] - g["pts_against"] for g in history])

        # Iterative SOS adjustment (simplified — 3 passes)
        sos = 0.0
        for _ in range(3):
            opp_pds = []
            for g in history:
                opp_hist = [
                    h for h in team_game_history[g["opponent"]]
                    if h["date"] < before_date
                ][-window:]
                if opp_hist:
                    opp_pd = np.mean([h["pts_for"] - h["pts_against"] for h in opp_hist])
                    opp_pds.append(opp_pd)
            sos = np.mean(opp_pds) if opp_pds else 0.0

        srs = pd + sos
        return round(float(np.clip(srs, -20.0, 20.0)), 3)

    for game in sorted_games:
        gid = game.get("game_id", "")
        home = game.get("home_team", "")
        away = game.get("away_team", "")
        date = game.get("game_date", "")

        home_srs = _compute_srs_at_date(home, date)
        away_srs = _compute_srs_at_date(away, date)

        srs_snapshot[gid] = {
            "home_srs": home_srs,
            "away_srs": away_srs,
            "srs_diff": round(home_srs - away_srs, 3),
        }

    log.info("SRS computed for %d games", len(srs_snapshot))
    return srs_snapshot


# ---------------------------------------------------------------------------
# Part 2: 5-season player log fetcher
# ---------------------------------------------------------------------------

def fetch_all_player_logs(seasons: list[str] | None = None) -> int:
    """
    Fetches player game logs for all 5 seasons using nba_api.
    Appends to data/player_game_logs.jsonl (deduplicates by player_id+game_id).
    Returns total new records written.
    """
    target_seasons = seasons or SEASONS

    existing = []
    if PLAYER_LOGS_PATH.exists():
        with open(PLAYER_LOGS_PATH) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        existing.append(json.loads(line))
                    except Exception:
                        pass

    existing_keys = {
        f"{r.get('player_id','')}_{r.get('game_id','')}": True
        for r in existing
    }
    log.info("Existing player log records: %d", len(existing))

    new_records = []

    for season in target_seasons:
        log.info("Fetching player logs for %s...", season)
        try:
            from nba_api.stats.endpoints import playergamelogs

            time.sleep(2.5)
            logs = playergamelogs.PlayerGameLogs(
                season_nullable=season,
                season_type_nullable="Regular Season",
            )
            df = logs.get_data_frames()[0]
            log.info("  Raw rows: %d", len(df))

            for _, row in df.iterrows():
                pid = str(row.get("PLAYER_ID", ""))
                gid = str(row.get("GAME_ID", ""))
                key = f"{pid}_{gid}"

                if key in existing_keys:
                    continue

                matchup = str(row.get("MATCHUP", ""))
                min_val = row.get("MIN", 0)
                try:
                    mins = float(min_val) if min_val else 0.0
                except (ValueError, TypeError):
                    mins = 0.0

                usage = float(row.get("USG_PCT", 0.20) or 0.20)
                ts = float(row.get("TS_PCT", 0.55) or 0.55)

                record = {
                    "player_id": pid,
                    "player_name": str(row.get("PLAYER_NAME", "")),
                    "team": str(row.get("TEAM_ABBREVIATION", "")),
                    "game_id": gid,
                    "game_date": str(row.get("GAME_DATE", "")),
                    "season": season,
                    "points": float(row.get("PTS", 0) or 0),
                    "assists": float(row.get("AST", 0) or 0),
                    "rebounds": float(row.get("REB", 0) or 0),
                    "threes_made": float(row.get("FG3M", 0) or 0),
                    "steals": float(row.get("STL", 0) or 0),
                    "blocks": float(row.get("BLK", 0) or 0),
                    "minutes": mins,
                    "usage_rate": usage,
                    "true_shooting_pct": ts,
                    "plus_minus": float(row.get("PLUS_MINUS", 0) or 0),
                    "is_home": "vs." in matchup,
                    "rest_days": 2,
                    "is_b2b": False,
                    "night_type": None,
                    "source": "nba_api",
                }
                new_records.append(record)
                existing_keys[key] = True

            log.info("  New records for %s: %d", season, len([r for r in new_records if r["season"] == season]))
            time.sleep(1.5)  # rate limit

        except ImportError:
            log.error("nba_api not installed — cannot fetch player logs")
            return 0
        except Exception as exc:
            log.warning("Player log fetch failed for %s: %s", season, exc)
            # Try balldontlie fallback
            try:
                from src.pipeline.bball_ref_fallback import fetch_balldontlie_player_stats
                bdl = fetch_balldontlie_player_stats(season=season)
                for r in bdl:
                    key = f"{r.get('player_id','')}_{r.get('game_id','')}"
                    if key not in existing_keys:
                        r["season"] = season
                        new_records.append(r)
                        existing_keys[key] = True
                log.info("  Balldontlie fallback: %d records for %s", len(bdl), season)
            except Exception as exc2:
                log.warning("  Balldontlie also failed: %s", exc2)

    if new_records:
        with open(PLAYER_LOGS_PATH, "a") as f:
            for r in new_records:
                f.write(json.dumps(r) + "\n")
        log.info("Wrote %d new player log records to %s", len(new_records), PLAYER_LOGS_PATH)
    else:
        log.info("No new player log records to write")

    return len(new_records)


# ---------------------------------------------------------------------------
# Part 3: Expanded 50-feature vector
# ---------------------------------------------------------------------------
#
# New features added (indices 42-49):
#   [42] elo_diff_norm        — (home_elo - away_elo) / 400, normalized
#   [43] home_elo_wp          — Elo-implied win probability for home team
#   [44] home_srs_norm        — home SRS / 20 (SRS range ≈ -15 to +15)
#   [45] away_srs_norm        — away SRS / 20
#   [46] srs_diff_norm        — (home_srs - away_srs) / 20
#   [47] home_streak          — current win/loss streak (-1 to +1)
#   [48] away_streak          — current win/loss streak (-1 to +1)
#   [49] season_progress      — fraction of season elapsed (0-1)
#
# These 8 features address the main information gaps in the current vector.
# Elo alone (index 42-43) is expected to add ~0.03-0.05 AUC.

NEW_FEATURE_NAMES = [
    "elo_diff_norm",
    "home_elo_wp",
    "home_srs_norm",
    "away_srs_norm",
    "srs_diff_norm",
    "home_streak",
    "away_streak",
    "season_progress",
]
NEW_FEATURE_DIM = 50
NEW_FEATURE_START_IDX = 42


def compute_streak(
    team_games: list[dict],
    before_date: str,
    max_streak: int = 10,
) -> float:
    """
    Current win/loss streak for a team before a given date.
    Returns value in [-1, 1]: +1 = 10-game win streak, -1 = 10-game loss streak.
    """
    # history is already sorted and filtered for this team
    prior = [g for g in team_games if g.get("game_date", "") < before_date]

    if not prior:
        return 0.0

    # Walk backwards from most recent game
    streak = 0
    last_result = None

    for game in reversed(prior):
        is_home = game.get("home_team") == game["team_of_interest"]
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


def build_upgraded_feature_vector(
    game: dict,
    all_games: list[dict],
    team_histories: dict[str, list[dict]],
    elo_data: dict,
    srs_data: dict,
    # Pass-through from enrich_features
    causal_wp_adjustment: float = 0.0,
    injury_impact_home: float = 0.0,
    injury_impact_away: float = 0.0,
    referee_foul_rate: float = 1.0,
) -> np.ndarray:
    # Base 50 features (now includes Group G)
    vec = engineer_features(
        game_log=game,
        all_game_logs=all_games,
        causal_wp_adjustment=causal_wp_adjustment,
        injury_impact_home=injury_impact_home,
        injury_impact_away=injury_impact_away,
        referee_foul_rate=referee_foul_rate,
        elo_data=elo_data,
        srs_data=srs_data,
        team_histories=team_histories,
    )

    # Patch enrich_features placeholders directly
    vec[16] = float(game.get("home_games_played_norm", 0.5))
    vec[17] = float(game.get("away_games_played_norm", 0.5))
    vec[22] = float(game.get("is_playoff", 0.0))
    vec[23] = float(game.get("game_number_norm", 0.5))
    vec[36] = float(game.get("home_sos_norm", 0.5))
    vec[37] = float(game.get("away_sos_norm", 0.5))

    return vec


def build_upgraded_feature_matrix(
    games: list[dict],
    elo_data: dict,
    srs_data: dict,
) -> tuple[np.ndarray, np.ndarray]:
    """Build the full 50-feature X matrix and y labels."""
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

    # Pre-index team histories for faster lookups
    team_histories: dict[str, list[dict]] = defaultdict(list)
    for g in sorted(games, key=lambda x: x.get("game_date", "")):
        h, a = g.get("home_team"), g.get("away_team")
        gh = g.copy()
        gh["team_of_interest"] = h
        team_histories[h].append(gh)
        ga = g.copy()
        ga["team_of_interest"] = a
        team_histories[a].append(ga)

    X_rows = []
    y_rows = []

    for game in games:
        vec = build_upgraded_feature_vector(
            game=game,
            all_games=games,
            team_histories=team_histories,
            elo_data=elo_data,
            srs_data=srs_data,
            causal_wp_adjustment=game.get("causal_wp_adj", 0.0),
            injury_impact_home=game.get("injury_impact_home", 0.0),
            injury_impact_away=game.get("injury_impact_away", 0.0),
            referee_foul_rate=game.get("referee_foul_rate_norm", 1.0),
        )

        assert len(vec) == NEW_FEATURE_DIM, f"Expected {NEW_FEATURE_DIM}, got {len(vec)}"
        X_rows.append(vec)
        y_rows.append(float(game.get("home_win", 0)))

    X = np.stack(X_rows).astype(np.float32)
    y = np.array(y_rows, dtype=np.float32)

    # Sanitize
    nan_count = int(np.isnan(X).sum())
    if nan_count > 0:
        log.warning("Replacing %d NaN values in feature matrix", nan_count)
        X = np.nan_to_num(X, nan=0.0)

    log.info("Upgraded feature matrix: X=%s y=%s", X.shape, y.shape)
    return X, y


# ---------------------------------------------------------------------------
# Retrain with recalibrated targets
# ---------------------------------------------------------------------------

def retrain_with_new_targets(X: np.ndarray, y: np.ndarray) -> dict:
    """
    Retrain ensemble with:
    - Corrected AUC targets (0.680 pre-game, not 0.870)
    - Larger RF (500 trees) to handle 50-feature vector
    - Isotonic calibration instead of Platt scaling (better for larger datasets)
    """
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

    from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import roc_auc_score, brier_score_loss
    from sklearn.calibration import CalibratedClassifierCV
    import pickle

    MODEL_PATH = Path("data/models/ensemble_model_v2.pkl")
    META_PATH = Path("data/models/ensemble_meta_v2.json")

    if len(X) < 200:
        raise ValueError(f"Need at least 200 samples, got {len(X)}")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42, stratify=y
    )
    log.info("Training: %d samples, test: %d samples", len(X_train), len(X_test))

    # RF — larger for 50 features
    log.info("Training Random Forest (500 trees, 50 features)...")
    rf_base = RandomForestClassifier(
        n_estimators=500,
        max_depth=10,
        min_samples_leaf=8,
        max_features="sqrt",
        class_weight="balanced",
        random_state=42,
        n_jobs=-1,
    )
    rf_model = CalibratedClassifierCV(rf_base, method="isotonic", cv=5)
    rf_model.fit(X_train, y_train)
    rf_probs = rf_model.predict_proba(X_test)[:, 1]
    rf_auc = roc_auc_score(y_test, rf_probs)
    rf_brier = brier_score_loss(y_test, rf_probs)
    log.info("RF: AUC=%.4f, Brier=%.4f", rf_auc, rf_brier)

    # GBM / XGBoost
    log.info("Training XGBoost/GBM...")
    try:
        from xgboost import XGBClassifier
        xgb_base = XGBClassifier(
            n_estimators=400,
            max_depth=6,
            learning_rate=0.04,
            subsample=0.8,
            colsample_bytree=0.8,
            min_child_weight=8,
            random_state=42,
            eval_metric="logloss",
            verbosity=0,
            use_label_encoder=False,
        )
    except ImportError:
        xgb_base = GradientBoostingClassifier(
            n_estimators=400,
            max_depth=5,
            learning_rate=0.04,
            subsample=0.8,
            random_state=42,
        )

    xgb_model = CalibratedClassifierCV(xgb_base, method="isotonic", cv=5)
    xgb_model.fit(X_train, y_train)
    xgb_probs = xgb_model.predict_proba(X_test)[:, 1]
    xgb_auc = roc_auc_score(y_test, xgb_probs)
    xgb_brier = brier_score_loss(y_test, xgb_probs)
    log.info("XGB: AUC=%.4f, Brier=%.4f", xgb_auc, xgb_brier)

    # Ensemble
    ensemble_probs = 0.45 * rf_probs + 0.55 * xgb_probs
    ensemble_auc = roc_auc_score(y_test, ensemble_probs)
    ensemble_brier = brier_score_loss(y_test, ensemble_probs)
    log.info("Ensemble: AUC=%.4f, Brier=%.4f", ensemble_auc, ensemble_brier)

    # Evaluate against realistic targets
    target_met = ensemble_auc >= PRE_GAME_AUC_TARGET
    minimum_met = ensemble_auc >= PRE_GAME_AUC_MINIMUM
    brier_ok = ensemble_brier <= PRE_GAME_BRIER_TARGET

    if target_met:
        log.info("TARGET MET: AUC %.4f >= %.3f", ensemble_auc, PRE_GAME_AUC_TARGET)
    elif minimum_met:
        log.info("MINIMUM MET: AUC %.4f >= %.3f (target is %.3f)",
                 ensemble_auc, PRE_GAME_AUC_MINIMUM, PRE_GAME_AUC_TARGET)
    else:
        log.warning("BELOW MINIMUM: AUC %.4f < %.3f — check feature pipeline",
                    ensemble_auc, PRE_GAME_AUC_MINIMUM)

    # Feature importance
    rf_inner = rf_base
    rf_inner.fit(X_train, y_train)  # refit base for importances
    all_feature_names = []
    try:
        from src.ml.feature_engineer import FEATURE_NAMES as BASE_NAMES
        all_feature_names = list(BASE_NAMES) + NEW_FEATURE_NAMES
    except Exception:
        all_feature_names = [f"feat_{i}" for i in range(NEW_FEATURE_DIM)]

    importances = rf_inner.feature_importances_
    top_features = []
    if len(importances) == len(all_feature_names):
        idx = np.argsort(importances)[::-1][:15]
        top_features = [
            {"feature": all_feature_names[i], "importance": round(float(importances[i]), 4)}
            for i in idx
        ]

    # Save
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(MODEL_PATH, "wb") as f:
        pickle.dump({"rf": rf_model, "xgb": xgb_model, "feature_dim": NEW_FEATURE_DIM}, f)

    meta = {
        "version": "v2_upgraded",
        "feature_dim": NEW_FEATURE_DIM,
        "rf_auc": round(rf_auc, 4),
        "xgb_auc": round(xgb_auc, 4),
        "ensemble_auc": round(ensemble_auc, 4),
        "rf_brier": round(rf_brier, 4),
        "xgb_brier": round(xgb_brier, 4),
        "ensemble_brier": round(ensemble_brier, 4),
        "training_samples": len(X_train),
        "test_samples": len(X_test),
        "target_met": target_met,
        "minimum_met": minimum_met,
        "brier_target_met": brier_ok,
        "auc_target": PRE_GAME_AUC_TARGET,
        "auc_minimum": PRE_GAME_AUC_MINIMUM,
        "brier_target": PRE_GAME_BRIER_TARGET,
        "top_features": top_features,
        "note": (
            "Pre-game NBA prediction AUC ceiling with box-score features is ~0.68-0.72. "
            "The previous 0.870 target was based on synthetic in-game data and is not "
            "achievable pre-game. In-game model (0.969 AUC) remains the primary predictor."
        ),
        "trained_at": datetime.now().isoformat(),
    }

    with open(META_PATH, "w") as f:
        json.dump(meta, f, indent=2)

    log.info("Model saved to %s", MODEL_PATH)
    return meta


# ---------------------------------------------------------------------------
# Load helpers
# ---------------------------------------------------------------------------

def _load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        log.warning("File not found: %s", path)
        return []
    records = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except Exception:
                    pass
    return records


def load_best_available_games() -> list[dict]:
    """Load enriched games if available, fall back to raw game logs."""
    # Prefer enriched (has injury_impact, sos, games_played etc.)
    if ENRICHED_PATH.exists():
        games = _load_jsonl(ENRICHED_PATH)
        if games:
            log.info("Loaded %d enriched games from %s", len(games), ENRICHED_PATH)
            return games

    # Fall back to consolidated game log
    if GAME_LOGS_PATH.exists():
        games = _load_jsonl(GAME_LOGS_PATH)
        if games:
            log.info("Loaded %d games from %s", len(games), GAME_LOGS_PATH)
            return games

    # Fall back to per-season JSONL
    all_games: dict[str, dict] = {}
    for path in sorted(REAL_DATA_DIR.glob("games_*.jsonl")):
        for r in _load_jsonl(path):
            gid = r.get("game_id", "")
            if gid and gid not in all_games:
                all_games[gid] = {
                    "game_id": gid,
                    "season": r.get("season", ""),
                    "game_date": r.get("game_date", ""),
                    "home_team": r.get("home_team", ""),
                    "away_team": r.get("away_team", ""),
                    "home_score": r.get("final_home", 0),
                    "away_score": r.get("final_away", 0),
                    "home_win": 1 if r.get("final_home", 0) > r.get("final_away", 0) else 0,
                    "source": r.get("source", ""),
                }

    games = list(all_games.values())
    games.sort(key=lambda g: g.get("game_date", ""))
    log.info("Loaded %d games from per-season JSONL files", len(games))
    return games


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

async def run_upgrade(
    fetch_player_logs: bool = True,
    dry_run: bool = False,
    skip_srs: bool = False,
) -> dict:
    start = datetime.now()

    # Load games
    games = load_best_available_games()
    if not games:
        log.error("No game data found. Run real_data_pipeline first.")
        return {}

    log.info("Loaded %d games total", len(games))

    # Part 2: Player logs (5 seasons)
    new_player_records = 0
    if fetch_player_logs:
        log.info("Part 2: Fetching 5-season player logs...")
        new_player_records = fetch_all_player_logs(SEASONS)

        # Re-run injury detection with expanded player logs
        if new_player_records > 0:
            log.info("Re-running injury detection with expanded player logs...")
            try:
                import subprocess, sys
                subprocess.run(
                    [sys.executable, "-m", "src.pipeline.ingest_injury_history"],
                    capture_output=False, check=False,
                )
            except Exception as exc:
                log.warning("Injury re-detection failed: %s", exc)

        # Reload injury-enriched games
        games = load_best_available_games()

    # Part 1: Elo ratings
    log.info("Part 1: Computing Elo ratings...")
    elo_data = compute_elo_ratings(games)
    ELO_CACHE_PATH.write_text(json.dumps(elo_data, indent=2))
    log.info("Elo ratings cached to %s", ELO_CACHE_PATH)

    # Part 1b: SRS ratings
    if os.environ.get("SKIP_SRS") == "1" or skip_srs:
        if SRS_CACHE_PATH.exists():
            log.info("Loading SRS ratings from cache...")
            srs_data = json.loads(SRS_CACHE_PATH.read_text())
        else:
            log.info("Part 1b: Computing SRS ratings (cache not found)...")
            srs_data = compute_srs_ratings(games)
            SRS_CACHE_PATH.write_text(json.dumps(srs_data, indent=2))
    else:
        log.info("Part 1b: Computing SRS ratings...")
        srs_data = compute_srs_ratings(games)
        SRS_CACHE_PATH.write_text(json.dumps(srs_data, indent=2))
        log.info("SRS ratings cached to %s", SRS_CACHE_PATH)

    # Spot check Elo distribution
    elo_diffs = [v.get("elo_diff", 0) for v in elo_data.values()]
    log.info(
        "Elo diff stats — mean: %.1f, std: %.1f, min: %.1f, max: %.1f",
        np.mean(elo_diffs), np.std(elo_diffs), np.min(elo_diffs), np.max(elo_diffs),
    )

    if dry_run:
        log.info("Dry run — stopping before feature matrix build")
        return {
            "games": len(games),
            "elo_computed": len(elo_data),
            "srs_computed": len(srs_data),
            "new_player_records": new_player_records,
        }

    # Part 3: Build upgraded feature matrix
    log.info("Part 3: Building 50-feature matrix...")
    X, y = build_upgraded_feature_matrix(games, elo_data, srs_data)

    # Retrain
    log.info("Retraining ensemble with upgraded features...")
    training_report = retrain_with_new_targets(X, y)

    end = datetime.now()
    report = {
        "started_at": start.isoformat(),
        "completed_at": end.isoformat(),
        "duration_seconds": (end - start).total_seconds(),
        "games_used": len(games),
        "new_player_records": new_player_records,
        "feature_dim": NEW_FEATURE_DIM,
        "new_features": NEW_FEATURE_NAMES,
        "training": training_report,
        "auc_targets": {
            "pre_game_target": PRE_GAME_AUC_TARGET,
            "pre_game_minimum": PRE_GAME_AUC_MINIMUM,
            "in_game_achieved": 0.969,
            "note": "Pre-game ceiling ~0.68-0.72. In-game model is the primary predictor.",
        },
    }

    REPORT_PATH.write_text(json.dumps(report, indent=2))
    log.info("Upgrade complete. Report: %s", REPORT_PATH)
    return report


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Epoch Engine — Ensemble Upgrade")
    parser.add_argument("--elo-only", action="store_true",
                        help="Only compute Elo/SRS, skip player log fetch and retrain")
    parser.add_argument("--no-player-logs", action="store_true",
                        help="Skip 5-season player log fetch")
    parser.add_argument("--dry-run", action="store_true",
                        help="Compute features but don't retrain")
    parser.add_argument("--skip-srs", action="store_true",
                        help="Skip SRS computation and use cache if available")
    args = parser.parse_args()

    import asyncio

    if args.elo_only:
        games = load_best_available_games()
        elo_data = compute_elo_ratings(games)
        ELO_CACHE_PATH.write_text(json.dumps(elo_data, indent=2))
        srs_data = compute_srs_ratings(games)
        SRS_CACHE_PATH.write_text(json.dumps(srs_data, indent=2))
        log.info("Elo and SRS computed. Run without --elo-only to retrain.")
        return

    report = asyncio.run(run_upgrade(
        fetch_player_logs=not args.no_player_logs,
        dry_run=args.dry_run,
        skip_srs=args.skip_srs,
    ))

    if report:
        auc = report.get("training", {}).get("ensemble_auc", 0)
        target = PRE_GAME_AUC_TARGET
        log.info("Final ensemble AUC: %.4f (target: %.3f)", auc, target)


if __name__ == "__main__":
    main()
