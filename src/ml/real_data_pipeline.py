"""
Real Data Pipeline — SESSION D Week 1
Pulls NBA data with three-tier fallback:
  Tier 1   → nba_api
  Tier 2.5 → balldontlie (free JSON, never goes down)
  Tier 3   → Basketball Reference HTML scraper

Pure functions. Constants at module level. No magic numbers.
"""

from __future__ import annotations

import json
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

from src.pipeline.bball_ref_fallback import (
    DATA_SOURCE_BALLDONTLIE,
    DATA_SOURCE_FALLBACK,
    DATA_SOURCE_PRIMARY,
    fetch_balldontlie_games,
    fetch_balldontlie_player_stats,
    nba_api_with_fallback,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
NBA_API_RETRY_ATTEMPTS: int = 3
NBA_API_RETRY_BASE_DELAY: float = 2.0
NBA_API_RETRY_MAX_DELAY: float = 30.0
NBA_API_CALL_DELAY: float = 0.6

SEASONS_TO_PULL: list[str] = ["2022-23", "2023-24", "2024-25"]
MIN_PLAYER_GAMES: int = 20
MAX_PLAYERS_DEFAULT: int = 150

# Night type z-score thresholds
NIGHT_TYPE_COLD_Z: float = -1.5
NIGHT_TYPE_BELOW_AVG_Z: float = -0.5
NIGHT_TYPE_ABOVE_AVG_Z: float = 0.5
NIGHT_TYPE_HOT_Z: float = 1.5
NIGHT_TYPE_MIN_HISTORY: int = 5
NIGHT_TYPE_MIN_STD: float = 1.0

# Injury proxy: games > this many std below team avg ortg
INJURY_PROXY_Z_THRESHOLD: float = -1.5
INJURY_PROXY_WP_DELTA_SCALE: float = -0.05
DEFAULT_PLAYER_USAGE: float = 0.25
DEFAULT_ORTG: float = 110.0
DEFAULT_ORTG_STD: float = 5.0
DEFAULT_REST_DAYS: int = 3
DEFAULT_WIN_PCT: float = 0.500
DEFAULT_LAST_5_WINS: int = 2

# Altitude lookup by team (feet above sea level)
TEAM_ALTITUDE_FT: dict[str, int] = {
    "DEN": 5280, "UTA": 4226, "OKC": 1201, "DAL": 430,
    "SAS": 650,  "PHX": 1086, "GSW": 52,   "LAL": 233,
    "LAC": 233,  "SAC": 30,   "POR": 50,   "SEA": 520,
    "MEM": 285,  "NOP": 6,    "HOU": 43,   "MIN": 830,
    "CHI": 597,  "MIL": 617,  "IND": 715,  "DET": 585,
    "CLE": 653,  "TOR": 249,  "BOS": 141,  "NYK": 33,
    "BKN": 33,   "PHI": 39,   "WAS": 25,   "ATL": 1050,
    "MIA": 6,    "ORL": 96,   "CHA": 748,
}
DEFAULT_ALTITUDE_FT: int = 500

OUTPUT_DIR = Path("data")
GAME_LOGS_PATH = OUTPUT_DIR / "real_game_logs.jsonl"
INJURY_LOGS_PATH = OUTPUT_DIR / "injury_game_logs.jsonl"
PLAYER_LOGS_PATH = OUTPUT_DIR / "player_game_logs.jsonl"


# ---------------------------------------------------------------------------
# nba_api wrappers
# ---------------------------------------------------------------------------

def _nba_api_call_with_retry(func, *args, **kwargs):
    for attempt in range(NBA_API_RETRY_ATTEMPTS):
        try:
            time.sleep(NBA_API_CALL_DELAY)
            return func(*args, **kwargs)
        except Exception as exc:
            if attempt == NBA_API_RETRY_ATTEMPTS - 1:
                raise
            delay = min(
                NBA_API_RETRY_BASE_DELAY * (2 ** attempt),
                NBA_API_RETRY_MAX_DELAY,
            )
            print(f"  Retry {attempt + 1}/{NBA_API_RETRY_ATTEMPTS} after {delay}s: {exc}")
            time.sleep(delay)


def _pull_team_game_logs_nba_api(season: str) -> list[dict[str, Any]]:
    try:
        from nba_api.stats.endpoints import leaguegamelog
        logs = _nba_api_call_with_retry(
            leaguegamelog.LeagueGameLog,
            season=season,
            season_type_all_star="Regular Season",
        )
        df = logs.get_data_frames()[0]
        return df.to_dict("records")
    except ImportError:
        print("Warning: nba_api not available — will try balldontlie")
        raise
    except Exception as exc:
        print(f"Warning pulling team game logs for {season}: {exc}")
        raise


def _pull_player_game_logs_nba_api(
    season: str,
    max_players: int = MAX_PLAYERS_DEFAULT,
) -> list[dict[str, Any]]:
    try:
        from nba_api.stats.endpoints import playergamelogs
        logs = _nba_api_call_with_retry(
            playergamelogs.PlayerGameLogs,
            season_nullable=season,
            season_type_nullable="Regular Season",
        )
        df = logs.get_data_frames()[0]
        top_players = (
            df.groupby("PLAYER_ID")["MIN"]
            .sum()
            .nlargest(max_players)
            .index
        )
        df = df[df["PLAYER_ID"].isin(top_players)]
        return df.to_dict("records")
    except ImportError:
        print("Warning: nba_api not available — will try balldontlie")
        raise
    except Exception as exc:
        print(f"Warning pulling player game logs for {season}: {exc}")
        raise


# ---------------------------------------------------------------------------
# Public pull functions — with fallback chain
# ---------------------------------------------------------------------------

def pull_team_game_logs(season: str) -> tuple[list[dict[str, Any]], str]:
    """
    Pull team game logs with three-tier fallback.
    Returns (records, source_label).
    """
    records, source = nba_api_with_fallback(
        _pull_team_game_logs_nba_api,
        season,
        season=season,
    )
    print(f"  Team game logs source: {source} ({len(records)} records)")
    return records, source


def pull_player_game_logs(
    season: str,
    max_players: int = MAX_PLAYERS_DEFAULT,
) -> tuple[list[dict[str, Any]], str]:
    """
    Pull player game logs with three-tier fallback.
    Returns (records, source_label).
    """
    # nba_api gives rich player data — try it first
    for attempt in range(NBA_API_RETRY_ATTEMPTS):
        try:
            time.sleep(NBA_API_CALL_DELAY)
            records = _pull_player_game_logs_nba_api(season, max_players)
            print(f"  Player logs source: {DATA_SOURCE_PRIMARY} ({len(records)} records)")
            return records, DATA_SOURCE_PRIMARY
        except Exception as exc:
            if attempt < NBA_API_RETRY_ATTEMPTS - 1:
                delay = min(NBA_API_RETRY_BASE_DELAY * (2 ** attempt), NBA_API_RETRY_MAX_DELAY)
                time.sleep(delay)

    # Tier 2.5 — balldontlie player stats
    try:
        bdl_records = fetch_balldontlie_player_stats(season=season)
        if bdl_records:
            print(f"  Player logs source: {DATA_SOURCE_BALLDONTLIE} ({len(bdl_records)} records)")
            return bdl_records, DATA_SOURCE_BALLDONTLIE
    except Exception as exc:
        print(f"  balldontlie player stats failed: {exc}")

    print(f"  All player log sources exhausted for {season}")
    return [], DATA_SOURCE_FALLBACK


# ---------------------------------------------------------------------------
# Structuring — pure functions
# ---------------------------------------------------------------------------

def compute_rolling_win_pct(
    team_games: list[dict[str, Any]],
    team: str,
    before_date: str,
    window: int = 82,
) -> float:
    prior = [
        g for g in team_games
        if g.get("TEAM_ABBREVIATION") == team
        and g.get("GAME_DATE", "") < before_date
    ][-window:]
    if not prior:
        return DEFAULT_WIN_PCT
    wins = sum(1 for g in prior if g.get("WL") == "W")
    return round(wins / len(prior), 4)


def compute_rest_days(
    team_games: list[dict[str, Any]],
    team: str,
    game_date: str,
) -> tuple[int, bool]:
    prior = sorted(
        [g for g in team_games
         if g.get("TEAM_ABBREVIATION") == team
         and g.get("GAME_DATE", "") < game_date],
        key=lambda x: x.get("GAME_DATE", ""),
    )
    if not prior:
        return DEFAULT_REST_DAYS, False
    last_date = prior[-1].get("GAME_DATE", "")
    try:
        last = datetime.strptime(last_date, "%Y-%m-%d").date()
        current = datetime.strptime(game_date, "%Y-%m-%d").date()
        rest = (current - last).days
        return rest, rest == 1
    except Exception:
        return DEFAULT_REST_DAYS, False


def structure_game_logs(
    raw_records: list[dict[str, Any]],
    season: str,
    source: str = DATA_SOURCE_PRIMARY,
) -> list[dict[str, Any]]:
    """
    Structure raw nba_api team game logs into Epoch game log format.
    Also handles balldontlie records (already structured — passes through).
    """
    # balldontlie records already have Epoch schema
    if source == DATA_SOURCE_BALLDONTLIE:
        return raw_records

    games: dict[str, list[dict]] = defaultdict(list)
    for record in raw_records:
        gid = record.get("GAME_ID", "")
        games[gid].append(record)

    structured = []
    for game_id, records in games.items():
        if len(records) != 2:
            continue
        home = next((r for r in records if "vs." in r.get("MATCHUP", "")), records[0])
        away = next((r for r in records if "@" in r.get("MATCHUP", "")), records[1])

        home_team = home.get("TEAM_ABBREVIATION", "")
        away_team = away.get("TEAM_ABBREVIATION", "")
        game_date = home.get("GAME_DATE", "")

        home_rest, home_b2b = compute_rest_days(raw_records, home_team, game_date)
        away_rest, away_b2b = compute_rest_days(raw_records, away_team, game_date)
        home_win_pct = compute_rolling_win_pct(raw_records, home_team, game_date)
        away_win_pct = compute_rolling_win_pct(raw_records, away_team, game_date)

        home_score = int(home.get("PTS", 0) or 0)
        away_score = int(away.get("PTS", 0) or 0)
        home_pace = float(home.get("PACE", 98.0) or 98.0) if "PACE" in home else 98.0
        away_pace = float(away.get("PACE", 98.0) or 98.0) if "PACE" in away else 98.0

        structured.append({
            "game_id": game_id,
            "season": season,
            "game_date": game_date,
            "home_team": home_team,
            "away_team": away_team,
            "home_score": home_score,
            "away_score": away_score,
            "home_win": 1 if home_score > away_score else 0,
            "home_ortg": float(home.get("E_OFF_RATING", DEFAULT_ORTG) or DEFAULT_ORTG),
            "away_ortg": float(away.get("E_OFF_RATING", DEFAULT_ORTG) or DEFAULT_ORTG),
            "home_drtg": float(home.get("E_DEF_RATING", DEFAULT_ORTG) or DEFAULT_ORTG),
            "away_drtg": float(away.get("E_DEF_RATING", DEFAULT_ORTG) or DEFAULT_ORTG),
            "home_pace": home_pace,
            "away_pace": away_pace,
            "home_rest_days": home_rest,
            "away_rest_days": away_rest,
            "home_is_b2b": home_b2b,
            "away_is_b2b": away_b2b,
            "home_win_pct_prior": home_win_pct,
            "away_win_pct_prior": away_win_pct,
            "home_last_5_wins": int(home.get("L5_W", DEFAULT_LAST_5_WINS) or DEFAULT_LAST_5_WINS),
            "away_last_5_wins": int(away.get("L5_W", DEFAULT_LAST_5_WINS) or DEFAULT_LAST_5_WINS),
            "home_road_trip_game": 0,
            "away_road_trip_game": 0,
            "home_altitude_ft": TEAM_ALTITUDE_FT.get(home_team, DEFAULT_ALTITUDE_FT),
            "away_altitude_ft": TEAM_ALTITUDE_FT.get(away_team, DEFAULT_ALTITUDE_FT),
            "referee_crew_id": "",
            "predicted_home_wp": None,
            "actual_home_win": 1 if home_score > away_score else 0,
            "source": source,
        })
    return structured


def structure_player_logs(
    raw_records: list[dict[str, Any]],
    season: str,
    source: str = DATA_SOURCE_PRIMARY,
) -> list[dict[str, Any]]:
    """Structure raw player logs. Handles both nba_api and balldontlie schemas."""
    # balldontlie already structured
    if source == DATA_SOURCE_BALLDONTLIE:
        return raw_records

    structured = []
    for r in raw_records:
        try:
            matchup = r.get("MATCHUP", "")
            structured.append({
                "player_id": str(r.get("PLAYER_ID", "")),
                "player_name": r.get("PLAYER_NAME", ""),
                "team": r.get("TEAM_ABBREVIATION", ""),
                "game_id": str(r.get("GAME_ID", "")),
                "game_date": r.get("GAME_DATE", ""),
                "season": season,
                "points": float(r.get("PTS", 0) or 0),
                "assists": float(r.get("AST", 0) or 0),
                "rebounds": float(r.get("REB", 0) or 0),
                "threes_made": float(r.get("FG3M", 0) or 0),
                "steals": float(r.get("STL", 0) or 0),
                "blocks": float(r.get("BLK", 0) or 0),
                "minutes": float(r.get("MIN", 0) or 0),
                "usage_rate": float(r.get("USG_PCT", 0.20) or 0.20),
                "true_shooting_pct": float(r.get("TS_PCT", 0.55) or 0.55),
                "plus_minus": float(r.get("PLUS_MINUS", 0) or 0),
                "is_home": "vs." in matchup,
                "rest_days": DEFAULT_REST_DAYS,
                "is_b2b": False,
                "night_type": None,
                "source": source,
            })
        except Exception:
            continue
    return structured


def label_night_types(player_logs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Label each player log with a night type based on personal scoring distribution."""
    player_points: dict[str, list[float]] = defaultdict(list)
    for log in player_logs:
        player_points[log["player_id"]].append(log["points"])

    labeled = []
    for log in player_logs:
        pid = log["player_id"]
        pts = log["points"]
        history = player_points[pid]

        if len(history) < NIGHT_TYPE_MIN_HISTORY:
            log["night_type"] = "average"
            labeled.append(log)
            continue

        mean = np.mean(history)
        std = max(float(np.std(history)), NIGHT_TYPE_MIN_STD)
        z = (pts - mean) / std

        if z < NIGHT_TYPE_COLD_Z:
            night_type = "cold"
        elif z < NIGHT_TYPE_BELOW_AVG_Z:
            night_type = "below_avg"
        elif z < NIGHT_TYPE_ABOVE_AVG_Z:
            night_type = "average"
        elif z < NIGHT_TYPE_HOT_Z:
            night_type = "above_avg"
        else:
            night_type = "hot"

        log["night_type"] = night_type
        labeled.append(log)
    return labeled


def _extract_injury_proxy_games(game_logs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Proxy for injury games: games where a team scored significantly below
    their season average ortg. Candidates for star-player-absent games.
    """
    team_ortgs: dict[str, list[float]] = defaultdict(list)
    for g in game_logs:
        team_ortgs[g["home_team"]].append(g["home_ortg"])
        team_ortgs[g["away_team"]].append(g["away_ortg"])

    team_avg = {t: np.mean(v) for t, v in team_ortgs.items() if v}
    team_std = {t: max(float(np.std(v)), DEFAULT_ORTG_STD) for t, v in team_ortgs.items() if v}

    proxies = []
    for g in game_logs:
        for side, team, ortg in [
            ("home", g["home_team"], g["home_ortg"]),
            ("away", g["away_team"], g["away_ortg"]),
        ]:
            avg = team_avg.get(team, DEFAULT_ORTG)
            std = team_std.get(team, DEFAULT_ORTG_STD)
            z = (ortg - avg) / std
            if z < INJURY_PROXY_Z_THRESHOLD:
                proxies.append({
                    "game_id": g["game_id"],
                    "game_date": g["game_date"],
                    "injured_team": team,
                    "injured_player": "UNKNOWN",
                    "injury_type": "proxy",
                    "player_usage_rate": DEFAULT_PLAYER_USAGE,
                    "player_ortg_impact": round(z * std, 3),
                    "team_ortg_before": avg,
                    "team_ortg_after": ortg,
                    "team_drtg_before": g[f"{side}_drtg"],
                    "team_drtg_after": g[f"{side}_drtg"],
                    "win_probability_delta": round(z * INJURY_PROXY_WP_DELTA_SCALE, 4),
                    "actual_outcome": g[f"{'home_win' if side == 'home' else 'home_win'}"],
                })
    return proxies


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_real_data_pipeline(
    seasons: list[str] | None = None,
    max_players: int = MAX_PLAYERS_DEFAULT,
) -> dict[str, Any]:
    """
    Pull all real NBA data with three-tier fallback, structure it,
    and write to output files. Returns summary stats.
    """
    seasons = seasons or SEASONS_TO_PULL
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    all_game_logs: list[dict] = []
    all_player_logs: list[dict] = []
    sources_used: dict[str, list[str]] = {"games": [], "players": []}

    for season in seasons:
        print(f"Pulling season {season}...")

        raw_team, team_source = pull_team_game_logs(season)
        if raw_team:
            game_logs = structure_game_logs(raw_team, season, source=team_source)
            all_game_logs.extend(game_logs)
            sources_used["games"].append(team_source)
            print(f"  Structured games: {len(game_logs)}")

        raw_player, player_source = pull_player_game_logs(season, max_players)
        if raw_player:
            player_logs = structure_player_logs(raw_player, season, source=player_source)
            all_player_logs.extend(player_logs)
            sources_used["players"].append(player_source)
            print(f"  Structured player logs: {len(player_logs)}")

    all_player_logs = label_night_types(all_player_logs)

    with open(GAME_LOGS_PATH, "w") as f:
        for log in all_game_logs:
            f.write(json.dumps(log) + "\n")

    with open(PLAYER_LOGS_PATH, "w") as f:
        for log in all_player_logs:
            f.write(json.dumps(log) + "\n")

    injury_logs = _extract_injury_proxy_games(all_game_logs)
    with open(INJURY_LOGS_PATH, "w") as f:
        for log in injury_logs:
            f.write(json.dumps(log) + "\n")

    return {
        "seasons_pulled": seasons,
        "total_games": len(all_game_logs),
        "total_player_logs": len(all_player_logs),
        "injury_proxy_games": len(injury_logs),
        "sources_used": sources_used,
        "output_files": [
            str(GAME_LOGS_PATH),
            str(PLAYER_LOGS_PATH),
            str(INJURY_LOGS_PATH),
        ],
    }


# ---------------------------------------------------------------------------
# Load helpers
# ---------------------------------------------------------------------------

def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    logs = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    logs.append(json.loads(line))
                except Exception:
                    continue
    return logs


def load_game_logs() -> list[dict[str, Any]]:
    return _load_jsonl(GAME_LOGS_PATH)


def load_player_logs() -> list[dict[str, Any]]:
    return _load_jsonl(PLAYER_LOGS_PATH)


def load_injury_logs() -> list[dict[str, Any]]:
    return _load_jsonl(INJURY_LOGS_PATH)
