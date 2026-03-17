"""
real_data_pipeline.py — Epoch Engine
=====================================
Replaces data/synthetic/games_10k.jsonl with real historical NBA game data.

Fetches game logs for all 30 teams across the last 5 seasons, builds feature
vectors that match WinProbabilityModel._extract_features() exactly, and writes
output as JSONL to data/real/games_YYYY.jsonl (one file per season).

Feature vector order (14 fields, MUST match WinProbabilityModel._extract_features):
  [0]  score_diff          — home_score - away_score at game state snapshot
  [1]  time_rem            — seconds remaining in game
  [2]  quarter             — current quarter (1-4)
  [3]  momentum            — estimated momentum (-1.0 to 1.0)
  [4]  home_rate           — home scoring rate (pts per 60s elapsed)
  [5]  away_rate           — away scoring rate (pts per 60s elapsed)
  [6]  defensive_spacing   — proxy from 3PA rate (0-100)
  [7]  paint_density       — proxy from paint touches / possessions (0-20)
  [8]  three_point_coverage — proxy from opponent 3PA allowed rate (0-100)
  [9]  pick_roll           — 1 if high P&R team, 0 otherwise
  [10] fast_break          — 1 if high transition team, 0 otherwise
  [11] open_shooter        — 1 if high corner 3 rate, 0 otherwise
  [12] fatigue_home        — back-to-back penalty (1.0 = fresh, 0.88 = b2b)
  [13] fatigue_away        — back-to-back penalty (1.0 = fresh, 0.88 = b2b)

Usage:
    python -m src.ml.real_data_pipeline
    python -m src.ml.real_data_pipeline --seasons 1  # just current season
    python -m src.ml.real_data_pipeline --validate-only
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import math
import random
import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterator

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SEASONS = ["2020-21", "2021-22", "2022-23", "2023-24", "2024-25"]

# WinProbabilityModel._extract_features field order — DO NOT REORDER
FEATURE_NAMES = [
    "score_diff",
    "time_rem",
    "quarter",
    "momentum",
    "home_rate",
    "away_rate",
    "defensive_spacing",
    "paint_density",
    "three_point_coverage",
    "pick_roll",
    "fast_break",
    "open_shooter",
    "fatigue_home",
    "fatigue_away",
]
FEATURE_COUNT = len(FEATURE_NAMES)  # must be 14

# Fatigue multipliers (applied to scoring rate proxies)
FATIGUE_B2B = 0.88
FATIGUE_FRESH = 1.0

# Snapshots per game — we sample N evenly-spaced game states per real game
# to generate training rows (mirrors how synthetic data works with i % 10 != 0)
SNAPSHOTS_PER_GAME = 8

# Rate limiting
NBA_API_REQUESTS_PER_MINUTE = 28        # conservative under 30 limit
NBA_API_SLEEP = 60.0 / NBA_API_REQUESTS_PER_MINUTE  # ~2.14s between calls
BACKOFF_BASE = 2.0
BACKOFF_MAX = 120.0
MAX_RETRIES = 3

# Data quality benchmarks (2024-25 season targets)
BENCHMARK_HOME_WIN_RATE = 0.574
BENCHMARK_AVG_PACE = 99.8
BENCHMARK_AVG_ORTG = 114.2
BENCHMARK_THREE_ATTEMPT_RATE = 0.394
BENCHMARK_OT_RATE = 0.061

OUTPUT_DIR = Path("data/real")
CHECKPOINT_FILE = Path("data/real/.checkpoint.json")
REPORT_PATH = Path("data/pipeline_report.json")
DB_PATH = Path("data/nba_history.db")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("real_data_pipeline")


# ---------------------------------------------------------------------------
# Checkpoint — resumability
# ---------------------------------------------------------------------------

def load_checkpoint() -> dict[str, set[str]]:
    """Returns {season: set_of_completed_game_ids}."""
    if not CHECKPOINT_FILE.exists():
        return {}
    try:
        raw = json.loads(CHECKPOINT_FILE.read_text())
        return {season: set(ids) for season, ids in raw.items()}
    except Exception:
        return {}


def save_checkpoint(completed: dict[str, set[str]]) -> None:
    CHECKPOINT_FILE.parent.mkdir(parents=True, exist_ok=True)
    serializable = {season: list(ids) for season, ids in completed.items()}
    CHECKPOINT_FILE.write_text(json.dumps(serializable, indent=2))


# ---------------------------------------------------------------------------
# Async rate-limited nba_api wrapper
# ---------------------------------------------------------------------------

async def _sleep_async(seconds: float) -> None:
    await asyncio.sleep(seconds)


async def fetch_with_backoff(fn, *args, label: str = "", **kwargs) -> Any | None:
    """
    Calls blocking nba_api function in a thread executor with exponential backoff.
    Returns None after MAX_RETRIES failures.
    """
    loop = asyncio.get_event_loop()
    delay = NBA_API_SLEEP
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            await _sleep_async(delay)
            result = await loop.run_in_executor(None, lambda: fn(*args, **kwargs))
            return result
        except Exception as exc:
            wait = min(BACKOFF_BASE ** attempt + random.uniform(0, 1), BACKOFF_MAX)
            log.warning(
                "[%s] attempt %d/%d failed: %s — retrying in %.1fs",
                label, attempt, MAX_RETRIES, exc, wait,
            )
            await _sleep_async(wait)
    log.error("[%s] exhausted %d retries", label, MAX_RETRIES)
    return None


# ---------------------------------------------------------------------------
# NBA API fetchers (non-blocking wrappers)
# ---------------------------------------------------------------------------

async def fetch_team_game_log(team_id: int, season: str) -> list[dict] | None:
    """Fetch full game log for one team/season. Returns list of game dicts."""
    try:
        from nba_api.stats.endpoints import teamgamelog
        from nba_api.stats.static import teams as nba_teams_static

        def _call():
            tgl = teamgamelog.TeamGameLog(
                team_id=team_id,
                season=season,
                season_type_all_star="Regular Season",
            )
            df = tgl.get_data_frames()[0]
            return df.to_dict("records")

        label = f"team_gamelog/{team_id}/{season}"
        return await fetch_with_backoff(_call, label=label)
    except ImportError:
        log.error("nba_api not installed — cannot fetch team game logs")
        return None


async def fetch_game_boxscore(game_id: str) -> dict | None:
    """Fetch per-team advanced stats for a single game."""
    try:
        from nba_api.stats.endpoints import boxscoresummaryv2, boxscoreadvancedv2

        def _call():
            adv = boxscoreadvancedv2.BoxScoreAdvancedV2(game_id=game_id)
            team_df = adv.get_data_frames()[1]  # index 1 = team stats
            return team_df.to_dict("records")

        label = f"boxscore/{game_id}"
        return await fetch_with_backoff(_call, label=label)
    except ImportError:
        return None


async def fetch_league_game_log(season: str) -> list[dict] | None:
    """
    Fetch the full league game log for a season in one call.
    More efficient than per-team fetches — one request gets every game.
    """
    try:
        from nba_api.stats.endpoints import leaguegamelog

        def _call():
            lgl = leaguegamelog.LeagueGameLog(
                season=season,
                season_type_all_star="Regular Season",
                direction="ASC",
            )
            df = lgl.get_data_frames()[0]
            return df.to_dict("records")

        label = f"league_gamelog/{season}"
        return await fetch_with_backoff(_call, label=label)
    except ImportError:
        log.error("nba_api not installed")
        return None


# ---------------------------------------------------------------------------
# Fallback to bball_ref / balldontlie
# ---------------------------------------------------------------------------

async def fetch_season_fallback(season: str) -> list[dict]:
    """
    Calls the existing three-tier fallback chain from bball_ref_fallback.py.
    Returns a list of game dicts in Epoch schema.
    """
    loop = asyncio.get_event_loop()
    try:
        from src.pipeline.bball_ref_fallback import (
            fetch_balldontlie_games,
            nba_api_with_fallback,
        )

        def _call():
            records, source = nba_api_with_fallback(
                lambda: [],  # primary already failed if we're here
                season=season,
            )
            return records, source

        result = await loop.run_in_executor(None, _call)
        if result:
            records, source = result
            log.info("fallback chain returned %d records for %s via %s", len(records), season, source)
            return records
    except Exception as exc:
        log.error("fallback chain failed for %s: %s", season, exc)
    return []


# ---------------------------------------------------------------------------
# Game state snapshot builder
# ---------------------------------------------------------------------------

def _estimate_momentum(quarter: int, clock: float, home_pts: int, away_pts: int,
                        home_prev_pts: int, away_prev_pts: int) -> float:
    """
    Estimate momentum from scoring run since last snapshot.
    Returns value in [-1.0, 1.0]. Positive = home team momentum.
    """
    home_run = home_pts - home_prev_pts
    away_run = away_pts - away_prev_pts
    diff = home_run - away_run
    # Normalise to ±1 (a 10-0 run = max momentum)
    return max(-1.0, min(1.0, diff / 10.0))


def build_snapshots_from_game(game: dict, team_stats: dict | None = None) -> list[dict]:
    """
    Given a completed NBA game dict, synthesise SNAPSHOTS_PER_GAME training rows.

    The game dict must contain at minimum:
      final_home, final_away, is_home_b2b, is_away_b2b,
      home_three_pct, away_three_pct, (optionally) home_pace, away_pace

    Each snapshot represents the game state at a point in time and is formatted
    to match WinProbabilityModel._process_games() input exactly.
    """
    final_home = int(game.get("final_home", 0))
    final_away = int(game.get("final_away", 0))
    is_home_b2b = bool(game.get("is_home_b2b", False))
    is_away_b2b = bool(game.get("is_away_b2b", False))
    home_3pct = float(game.get("home_three_pct", 0.36))
    away_3pct = float(game.get("away_three_pct", 0.36))
    home_pace = float(game.get("home_pace", 99.8))

    fatigue_home = FATIGUE_B2B if is_home_b2b else FATIGUE_FRESH
    fatigue_away = FATIGUE_B2B if is_away_b2b else FATIGUE_FRESH

    # Build proxy features from available box score data
    defensive_spacing = min(100.0, home_3pct * 250.0)     # 36% → 90
    paint_density = max(0.0, 10.0 - (home_3pct * 20.0))   # higher 3P → less paint
    three_point_coverage = min(100.0, away_3pct * 250.0)   # opponent's 3PA tendency
    pick_roll = 1 if home_pace > 101.0 else 0
    fast_break = 1 if home_pace > 102.0 else 0
    open_shooter = 1 if home_3pct > 0.39 else 0

    # Total game time = 4 quarters × 12 min = 2880 seconds
    total_time = 2880.0
    snapshots = []
    prev_home = 0
    prev_away = 0

    for i in range(SNAPSHOTS_PER_GAME):
        # Fraction of game elapsed (spread from 5% to 95%)
        frac = 0.05 + (i / (SNAPSHOTS_PER_GAME - 1)) * 0.90
        time_elapsed = frac * total_time
        time_rem = max(0.0, total_time - time_elapsed)

        # Interpolate score linearly (real games aren't linear but this is a
        # reasonable first-order approximation for training data generation)
        home_pts = int(round(final_home * frac))
        away_pts = int(round(final_away * frac))

        # Quarter and clock derived from time_elapsed
        quarter = min(4, int(time_elapsed / 720) + 1)
        clock = max(0.0, 720.0 - (time_elapsed % 720.0))

        score_diff = home_pts - away_pts
        home_rate = (home_pts / time_elapsed * 60.0) if time_elapsed > 0 else 0.0
        away_rate = (away_pts / time_elapsed * 60.0) if time_elapsed > 0 else 0.0
        momentum = _estimate_momentum(quarter, clock, home_pts, away_pts, prev_home, prev_away)

        snapshot = {
            # Game state (used by DummyState in _process_games)
            "quarter": quarter,
            "clock": clock,
            "home_score": home_pts,
            "away_score": away_pts,
            # Feature fields (used by _extract_features via extra_features dict)
            "momentum": momentum,
            "defensive_spacing": defensive_spacing,
            "paint_density": paint_density,
            "three_point_coverage": three_point_coverage,
            "pick_roll": pick_roll,
            "fast_break": fast_break,
            "open_shooter": open_shooter,
            "fatigue_home": fatigue_home,
            "fatigue_away": fatigue_away,
        }
        snapshots.append(snapshot)
        prev_home = home_pts
        prev_away = away_pts

    return snapshots


def normalize_nba_api_game(raw: dict, prev_game_date_home: str | None,
                            prev_game_date_away: str | None) -> dict | None:
    """
    Convert a raw LeagueGameLog row into Epoch game schema.
    Returns None if the row is incomplete or a duplicate (away team row).
    """
    # LeagueGameLog returns one row per team per game — only process HOME rows
    wl = str(raw.get("WL", "")).upper()
    matchup = str(raw.get("MATCHUP", ""))
    if "vs." not in matchup:
        return None  # skip road team rows (they have "@" in matchup)

    game_date_str = str(raw.get("GAME_DATE", ""))
    try:
        game_date = datetime.strptime(game_date_str, "%b %d, %Y")
    except ValueError:
        try:
            game_date = datetime.strptime(game_date_str, "%Y-%m-%d")
        except ValueError:
            return None

    home_team = matchup.split(" vs. ")[0].strip()
    away_team = matchup.split(" vs. ")[1].strip()

    home_pts = int(raw.get("PTS", 0))
    # We don't have away score in this row — derive from W/L and point differential
    plus_minus = float(raw.get("PLUS_MINUS", 0))
    away_pts = int(home_pts - plus_minus)

    if home_pts == 0 and away_pts == 0:
        return None

    # Back-to-back detection
    is_home_b2b = False
    if prev_game_date_home:
        try:
            prev_dt = datetime.strptime(prev_game_date_home, "%Y-%m-%d")
            is_home_b2b = (game_date - prev_dt).days == 1
        except ValueError:
            pass

    # 3PT proxies from box score
    fg3a = float(raw.get("FG3A", 0))
    fga = float(raw.get("FGA", 1))
    fg3m = float(raw.get("FG3M", 0))
    home_three_pct = (fg3m / fg3a) if fg3a > 0 else 0.36
    home_three_rate = (fg3a / fga) if fga > 0 else 0.39

    return {
        "game_id": str(raw.get("GAME_ID", "")),
        "season": str(raw.get("SEASON_ID", ""))[-4:],
        "game_date": game_date.strftime("%Y-%m-%d"),
        "home_team": home_team,
        "away_team": away_team,
        "final_home": home_pts,
        "final_away": away_pts,
        "is_home_b2b": is_home_b2b,
        "is_away_b2b": False,     # away B2B requires cross-team lookup — default safe
        "home_three_pct": home_three_pct,
        "away_three_pct": 0.36,   # not available in this row — use league average
        "home_pace": 99.8,        # not available here — use league average
        "source": "nba_api",
    }


def normalize_fallback_game(raw: dict) -> dict | None:
    """Convert a bball_ref_fallback Epoch schema game to pipeline game schema."""
    home_pts = int(raw.get("home_score", 0))
    away_pts = int(raw.get("away_score", 0))
    if home_pts == 0 and away_pts == 0:
        return None
    return {
        "game_id": str(raw.get("game_id", "")),
        "season": str(raw.get("season", ""))[:4],
        "game_date": str(raw.get("game_date", "")),
        "home_team": str(raw.get("home_team", "")),
        "away_team": str(raw.get("away_team", "")),
        "final_home": home_pts,
        "final_away": away_pts,
        "is_home_b2b": bool(raw.get("home_is_b2b", False)),
        "is_away_b2b": bool(raw.get("away_is_b2b", False)),
        "home_three_pct": 0.36,
        "away_three_pct": 0.36,
        "home_pace": float(raw.get("home_pace", 99.8)),
        "source": str(raw.get("source", "fallback")),
    }


# ---------------------------------------------------------------------------
# JSONL game record builder (WinProbabilityModel.train() compatible)
# ---------------------------------------------------------------------------

def build_training_record(game: dict) -> dict:
    """
    Build one JSONL record that WinProbabilityModel._process_games() can consume.

    Output schema:
    {
      "final_home": int,
      "final_away": int,
      "game_id": str,
      "game_date": str,
      "home_team": str,
      "away_team": str,
      "season": str,
      "source": str,
      "states": [ { ...snapshot fields... }, ... ]
    }
    """
    snapshots = build_snapshots_from_game(game)
    return {
        "final_home": game["final_home"],
        "final_away": game["final_away"],
        "game_id": game["game_id"],
        "game_date": game["game_date"],
        "home_team": game["home_team"],
        "away_team": game["away_team"],
        "season": game["season"],
        "source": game.get("source", "unknown"),
        "states": snapshots,
    }


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------

def validate_record(record: dict) -> list[str]:
    """
    Validates one training record against WinProbabilityModel._extract_features()
    requirements. Returns a list of error strings (empty = valid).
    """
    errors: list[str] = []

    required_top = ["final_home", "final_away", "states"]
    for f in required_top:
        if f not in record:
            errors.append(f"missing top-level field: {f}")

    states = record.get("states", [])
    if not states:
        errors.append("states list is empty")
        return errors

    required_state_fields = [
        "quarter", "clock", "home_score", "away_score", "momentum",
        "defensive_spacing", "paint_density", "three_point_coverage",
        "pick_roll", "fast_break", "open_shooter", "fatigue_home", "fatigue_away",
    ]

    for i, state in enumerate(states):
        for f in required_state_fields:
            if f not in state:
                errors.append(f"state[{i}] missing field: {f}")

        q = state.get("quarter", 0)
        if not (1 <= q <= 4):
            errors.append(f"state[{i}] invalid quarter: {q}")

        clock = state.get("clock", -1)
        if not (0 <= clock <= 720):
            errors.append(f"state[{i}] invalid clock: {clock}")

        for score_field in ("home_score", "away_score"):
            s = state.get(score_field, -1)
            if s < 0 or s > 200:
                errors.append(f"state[{i}] implausible {score_field}: {s}")

        fatigue_home = state.get("fatigue_home", -1)
        fatigue_away = state.get("fatigue_away", -1)
        if not (0.5 <= fatigue_home <= 1.0):
            errors.append(f"state[{i}] invalid fatigue_home: {fatigue_home}")
        if not (0.5 <= fatigue_away <= 1.0):
            errors.append(f"state[{i}] invalid fatigue_away: {fatigue_away}")

    return errors


def validate_feature_extraction(record: dict) -> bool:
    """
    Runs WinProbabilityModel._extract_features() on each state and confirms
    the output vector is exactly FEATURE_COUNT (14) elements long.
    Returns True if all states produce valid feature vectors.
    """
    try:
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
        from src.intelligence.win_probability import WinProbabilityModel

        model = WinProbabilityModel.__new__(WinProbabilityModel)

        class _State:
            def __init__(self, d: dict):
                self.quarter = d["quarter"]
                self.clock = d["clock"]
                self.home_score = d["home_score"]
                self.away_score = d["away_score"]

        for state in record.get("states", []):
            feats = model._extract_features(_State(state), state.get("momentum", 0.0), state)
            if len(feats) != FEATURE_COUNT:
                log.error(
                    "Feature vector length mismatch: got %d, expected %d",
                    len(feats), FEATURE_COUNT,
                )
                return False
        return True
    except Exception as exc:
        log.warning("Feature extraction validation failed: %s", exc)
        return False


# ---------------------------------------------------------------------------
# Data quality report
# ---------------------------------------------------------------------------

def compute_quality_report(jsonl_path: Path) -> dict:
    """
    Reads a season JSONL file and computes quality benchmarks.
    Returns a dict suitable for inclusion in pipeline_report.json.
    """
    games = []
    with open(jsonl_path) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    games.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    if not games:
        return {"error": "empty file", "path": str(jsonl_path)}

    total = len(games)
    home_wins = sum(1 for g in games if g["final_home"] > g["final_away"])
    ot_games = sum(
        1 for g in games
        if g["final_home"] + g["final_away"] > 230  # rough OT proxy
    )
    total_pts = [g["final_home"] + g["final_away"] for g in games]
    avg_total = sum(total_pts) / len(total_pts) if total_pts else 0

    # Compute mean 3PT proxy from first snapshot of each game
    three_pcts = []
    for g in games:
        states = g.get("states", [])
        if states:
            three_pcts.append(states[0].get("defensive_spacing", 90.0) / 250.0)
    avg_3pt_rate = sum(three_pcts) / len(three_pcts) if three_pcts else 0.0

    home_win_rate = home_wins / total
    ot_rate = ot_games / total

    # Benchmark diffs
    benchmarks = {
        "home_win_rate":       {"actual": round(home_win_rate, 3), "target": BENCHMARK_HOME_WIN_RATE,
                                "ok": abs(home_win_rate - BENCHMARK_HOME_WIN_RATE) < 0.03},
        "avg_total_pts":       {"actual": round(avg_total, 1), "target": 228.4,  # 114.2 × 2
                                "ok": abs(avg_total - 228.4) < 10},
        "three_attempt_rate":  {"actual": round(avg_3pt_rate, 3), "target": BENCHMARK_THREE_ATTEMPT_RATE,
                                "ok": abs(avg_3pt_rate - BENCHMARK_THREE_ATTEMPT_RATE) < 0.05},
        "ot_rate":             {"actual": round(ot_rate, 3), "target": BENCHMARK_OT_RATE,
                                "ok": abs(ot_rate - BENCHMARK_OT_RATE) < 0.02},
    }

    all_ok = all(v["ok"] for v in benchmarks.values())

    return {
        "path": str(jsonl_path),
        "total_games": total,
        "home_wins": home_wins,
        "benchmarks": benchmarks,
        "all_benchmarks_pass": all_ok,
        "generated_at": datetime.now().isoformat(),
    }


# ---------------------------------------------------------------------------
# SQLite persistence (optional — for downstream historical queries)
# ---------------------------------------------------------------------------

def write_games_to_db(games: list[dict], db_path: Path = DB_PATH) -> None:
    """
    Upserts completed game records into the SQLite history database.
    Table: real_games — lightweight summary only (not full snapshot data).
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(db_path))
    cur = con.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS real_games (
            game_id     TEXT PRIMARY KEY,
            season      TEXT,
            game_date   TEXT,
            home_team   TEXT,
            away_team   TEXT,
            final_home  INTEGER,
            final_away  INTEGER,
            is_home_b2b INTEGER,
            is_away_b2b INTEGER,
            source      TEXT,
            ingested_at TEXT
        )
    """)
    now = datetime.now().isoformat()
    for g in games:
        cur.execute("""
            INSERT OR REPLACE INTO real_games
            (game_id, season, game_date, home_team, away_team,
             final_home, final_away, is_home_b2b, is_away_b2b, source, ingested_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            g.get("game_id", ""),
            g.get("season", ""),
            g.get("game_date", ""),
            g.get("home_team", ""),
            g.get("away_team", ""),
            int(g.get("final_home", 0)),
            int(g.get("final_away", 0)),
            int(g.get("is_home_b2b", False)),
            int(g.get("is_away_b2b", False)),
            g.get("source", ""),
            now,
        ))
    con.commit()
    con.close()
    log.info("wrote %d games to SQLite at %s", len(games), db_path)


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

async def process_season(
    season: str,
    completed: dict[str, set[str]],
    validation_errors: list[str],
) -> dict:
    """
    Fetches, validates, and writes all games for one season.
    Updates `completed` in-place for checkpoint resumability.
    Returns a per-season report dict.
    """
    log.info("=== Processing season %s ===", season)
    season_completed = completed.setdefault(season, set())

    output_path = OUTPUT_DIR / f"games_{season[:4]}.jsonl"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # --- Fetch raw game log ---
    raw_games: list[dict] = []
    source_used = "nba_api"

    log.info("[%s] fetching league game log from nba_api...", season)
    raw_rows = await fetch_league_game_log(season)

    if raw_rows:
        # Build a prev_date lookup for B2B detection
        # {team: last_game_date_str}
        team_prev_date: dict[str, str] = {}
        for row in raw_rows:
            matchup = str(row.get("MATCHUP", ""))
            if "vs." not in matchup:
                continue
            home_team = matchup.split(" vs. ")[0].strip()
            game_date_str = str(row.get("GAME_DATE", ""))
            try:
                gd = datetime.strptime(game_date_str, "%b %d, %Y")
                game_date_iso = gd.strftime("%Y-%m-%d")
            except ValueError:
                game_date_iso = game_date_str

            prev = team_prev_date.get(home_team)
            normalized = normalize_nba_api_game(row, prev, None)
            if normalized:
                raw_games.append(normalized)
                team_prev_date[home_team] = game_date_iso
        log.info("[%s] normalized %d games from nba_api", season, len(raw_games))
    else:
        log.warning("[%s] nba_api failed — activating fallback chain", season)
        fallback_raw = await fetch_season_fallback(season)
        for r in fallback_raw:
            norm = normalize_fallback_game(r)
            if norm:
                raw_games.append(norm)
        source_used = "fallback"
        log.info("[%s] fallback returned %d games", season, len(raw_games))

    if not raw_games:
        log.error("[%s] zero games retrieved — skipping season", season)
        return {"season": season, "games": 0, "errors": 1, "source": source_used}

    # --- Write JSONL (append mode, skip already-completed game IDs) ---
    written = 0
    skipped = 0
    error_count = 0
    db_batch: list[dict] = []

    with open(output_path, "a") as out_f:
        for game in raw_games:
            gid = game.get("game_id", "")
            if gid in season_completed:
                skipped += 1
                continue

            record = build_training_record(game)

            # Schema validation
            errs = validate_record(record)
            if errs:
                for e in errs:
                    validation_errors.append(f"[{season}/{gid}] {e}")
                error_count += 1
                continue

            out_f.write(json.dumps(record) + "\n")
            season_completed.add(gid)
            db_batch.append(game)
            written += 1

            # Checkpoint every 50 games
            if written % 50 == 0:
                save_checkpoint(completed)
                log.info("[%s] checkpoint: %d written, %d skipped", season, written, skipped)

    # Persist to SQLite
    if db_batch:
        write_games_to_db(db_batch)

    save_checkpoint(completed)
    log.info(
        "[%s] done — written: %d, skipped: %d, errors: %d",
        season, written, skipped, error_count,
    )

    return {
        "season": season,
        "games_written": written,
        "games_skipped": skipped,
        "validation_errors": error_count,
        "source": source_used,
        "output": str(output_path),
    }


async def run_pipeline(seasons: list[str] | None = None) -> dict:
    """
    Main entry point. Processes all seasons sequentially (to respect rate limits).
    Returns final pipeline report dict.
    """
    target_seasons = seasons or SEASONS
    completed = load_checkpoint()
    validation_errors: list[str] = []
    season_reports: list[dict] = []

    start_time = datetime.now()
    log.info("Starting real_data_pipeline for seasons: %s", target_seasons)

    for season in target_seasons:
        report = await process_season(season, completed, validation_errors)
        season_reports.append(report)

    # --- Quality reports per season ---
    quality_reports: dict[str, dict] = {}
    for season in target_seasons:
        output_path = OUTPUT_DIR / f"games_{season[:4]}.jsonl"
        if output_path.exists():
            quality_reports[season] = compute_quality_report(output_path)

    # --- Feature extraction spot-check ---
    feature_ok = True
    for season in target_seasons:
        output_path = OUTPUT_DIR / f"games_{season[:4]}.jsonl"
        if output_path.exists():
            with open(output_path) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            record = json.loads(line)
                            feature_ok = validate_feature_extraction(record)
                            break  # spot check first record per season
                        except Exception:
                            pass

    # --- Final pipeline report ---
    end_time = datetime.now()
    total_written = sum(r.get("games_written", 0) for r in season_reports)
    total_errors = sum(r.get("validation_errors", 0) for r in season_reports)
    all_benchmarks_pass = all(
        q.get("all_benchmarks_pass", False) for q in quality_reports.values()
    )

    pipeline_report = {
        "pipeline": "real_data_pipeline",
        "started_at": start_time.isoformat(),
        "completed_at": end_time.isoformat(),
        "duration_seconds": (end_time - start_time).total_seconds(),
        "seasons_processed": target_seasons,
        "total_games_written": total_written,
        "total_validation_errors": total_errors,
        "feature_extraction_ok": feature_ok,
        "all_benchmarks_pass": all_benchmarks_pass,
        "season_reports": season_reports,
        "quality_reports": quality_reports,
        "validation_error_sample": validation_errors[:20],
    }

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(pipeline_report, indent=2))
    log.info("Pipeline complete. Report written to %s", REPORT_PATH)
    log.info(
        "Total: %d games written, %d errors, benchmarks_pass=%s",
        total_written, total_errors, all_benchmarks_pass,
    )

    return pipeline_report


# ---------------------------------------------------------------------------
# Validate-only mode (no fetching, just checks existing JSONL files)
# ---------------------------------------------------------------------------

def run_validate_only() -> None:
    log.info("Running validation-only mode on existing data/real/*.jsonl files")
    any_found = False
    for season in SEASONS:
        path = OUTPUT_DIR / f"games_{season[:4]}.jsonl"
        if not path.exists():
            log.warning("No file found: %s", path)
            continue
        any_found = True
        report = compute_quality_report(path)
        log.info("Quality report for %s:", season)
        for k, v in report.get("benchmarks", {}).items():
            status = "OK" if v["ok"] else "FAIL"
            log.info("  [%s] %s: actual=%.3f target=%.3f", status, k, v["actual"], v["target"])
        log.info("  all_pass=%s, total_games=%d", report["all_benchmarks_pass"], report["total_games"])

        # Feature extraction check (first record)
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        record = json.loads(line)
                        ok = validate_feature_extraction(record)
                        log.info("  feature_extraction_ok=%s", ok)
                    except Exception as exc:
                        log.error("  feature check failed: %s", exc)
                    break

    if not any_found:
        log.warning("No data/real/games_YYYY.jsonl files found. Run pipeline first.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Epoch Engine — Real Data Pipeline")
    parser.add_argument(
        "--seasons", type=int, default=5,
        help="Number of most recent seasons to fetch (1–5, default 5)",
    )
    parser.add_argument(
        "--validate-only", action="store_true",
        help="Skip fetching — validate existing JSONL files only",
    )
    parser.add_argument(
        "--clear-checkpoint", action="store_true",
        help="Delete the checkpoint file and re-fetch everything",
    )
    args = parser.parse_args()

    if args.clear_checkpoint and CHECKPOINT_FILE.exists():
        CHECKPOINT_FILE.unlink()
        log.info("Checkpoint cleared.")

    if args.validate_only:
        run_validate_only()
        return

    n = max(1, min(5, args.seasons))
    target_seasons = SEASONS[-n:]
    asyncio.run(run_pipeline(target_seasons))


if __name__ == "__main__":
    main()
