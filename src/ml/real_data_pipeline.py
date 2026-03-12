import json
import time
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import numpy as np

# Rate limiting constants
NBA_API_RETRY_ATTEMPTS = 3
NBA_API_RETRY_BASE_DELAY = 2.0   # seconds
NBA_API_RETRY_MAX_DELAY = 30.0   # seconds
NBA_API_CALL_DELAY = 0.6         # seconds between calls

# Season constants
SEASONS_TO_PULL = ["2022-23", "2023-24", "2024-25"]
MIN_PLAYER_GAMES = 20

# Altitude lookup by team (feet above sea level)
TEAM_ALTITUDE_FT = {
    "DEN": 5280, "UTA": 4226, "OKC": 1201, "DAL": 430,
    "SAS": 650,  "PHX": 1086, "GSW": 52,   "LAL": 233,
    "LAC": 233,  "SAC": 30,   "POR": 50,   "SEA": 520,
    "MEM": 285,  "NOP": 6,    "HOU": 43,   "MIN": 830,
    "CHI": 597,  "MIL": 617,  "IND": 715,  "DET": 585,
    "CLE": 653,  "TOR": 249,  "BOS": 141,  "NYK": 33,
    "BKN": 33,   "PHI": 39,   "WAS": 25,   "ATL": 1050,
    "MIA": 6,    "ORL": 96,   "CHA": 748,
}

OUTPUT_DIR = Path("data")
GAME_LOGS_PATH = OUTPUT_DIR / "real_game_logs.jsonl"
INJURY_LOGS_PATH = OUTPUT_DIR / "injury_game_logs.jsonl"
PLAYER_LOGS_PATH = OUTPUT_DIR / "player_game_logs.jsonl"

def _nba_api_call_with_retry(func, *args, **kwargs):
    """
    Call any nba_api function with retry + exponential backoff.
    Handles rate limiting gracefully.
    """
    for attempt in range(NBA_API_RETRY_ATTEMPTS):
        try:
            time.sleep(NBA_API_CALL_DELAY)
            return func(*args, **kwargs)
        except Exception as e:
            if attempt == NBA_API_RETRY_ATTEMPTS - 1:
                raise
            delay = min(
                NBA_API_RETRY_BASE_DELAY * (2 ** attempt),
                NBA_API_RETRY_MAX_DELAY
            )
            print(f"  Retry {attempt + 1}/{NBA_API_RETRY_ATTEMPTS} after {delay}s: {e}")
            time.sleep(delay)

def pull_team_game_logs(season: str) -> List[dict]:
    """
    Pull all team game logs for a season from nba_api.
    Returns list of raw game records.
    """
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
        print("Warning: nba_api not available — returning empty game logs")
        return []
    except Exception as e:
        print(f"Warning pulling team game logs for {season}: {e}")
        return []

def pull_player_game_logs(
    season: str,
    max_players: int = 200,
) -> List[dict]:
    """
    Pull per-player game logs for a season.
    Pulls top max_players by minutes played to stay within rate limits.
    """
    try:
        from nba_api.stats.endpoints import playergamelogs
        logs = _nba_api_call_with_retry(
            playergamelogs.PlayerGameLogs,
            season_nullable=season,
            season_type_nullable="Regular Season",
        )
        df = logs.get_data_frames()[0]
        # Limit to top players by minutes
        top_players = (
            df.groupby("PLAYER_ID")["MIN"]
            .sum()
            .nlargest(max_players)
            .index
        )
        df = df[df["PLAYER_ID"].isin(top_players)]
        return df.to_dict("records")
    except ImportError:
        print("Warning: nba_api not available — returning empty player logs")
        return []
    except Exception as e:
        print(f"Warning pulling player game logs for {season}: {e}")
        return []

def compute_rolling_win_pct(
    team_games: List[dict],
    team: str,
    before_date: str,
    window: int = 82,
) -> float:
    """Compute win percentage for a team in games before a given date."""
    prior_games = [
        g for g in team_games
        if g.get("TEAM_ABBREVIATION") == team
        and g.get("GAME_DATE", "") < before_date
    ][-window:]
    if not prior_games:
        return 0.500
    wins = sum(1 for g in prior_games if g.get("WL") == "W")
    return round(wins / len(prior_games), 4)

def compute_rest_days(
    team_games: List[dict],
    team: str,
    game_date: str,
) -> Tuple[int, bool]:
    """
    Compute days of rest and back-to-back status for a team
    before a given game date.
    Returns (rest_days, is_back_to_back).
    """
    prior_games = sorted([
        g for g in team_games
        if g.get("TEAM_ABBREVIATION") == team
        and g.get("GAME_DATE", "") < game_date
    ], key=lambda x: x.get("GAME_DATE", ""))

    if not prior_games:
        return 3, False

    last_game_date = prior_games[-1].get("GAME_DATE", "")
    try:
        last = datetime.strptime(last_game_date, "%Y-%m-%d").date()
        current = datetime.strptime(game_date, "%Y-%m-%d").date()
        rest = (current - last).days
        return rest, rest == 1
    except Exception:
        return 3, False

def structure_game_logs(
    raw_records: List[dict],
    season: str,
) -> List[dict]:
    """
    Structure raw nba_api team game logs into Epoch game log format.
    Pairs home and away records for each game.
    """
    # Group by game_id
    games: Dict[str, List[dict]] = {}
    for record in raw_records:
        gid = record.get("GAME_ID", "")
        if gid not in games:
            games[gid] = []
        games[gid].append(record)

    structured = []
    for game_id, records in games.items():
        if len(records) != 2:
            continue

        # Identify home and away
        home = next(
            (r for r in records if "vs." in r.get("MATCHUP", "")), records[0]
        )
        away = next(
            (r for r in records if "@" in r.get("MATCHUP", "")), records[1]
        )

        home_team = home.get("TEAM_ABBREVIATION", "")
        away_team = away.get("TEAM_ABBREVIATION", "")
        game_date = home.get("GAME_DATE", "")

        home_rest, home_b2b = compute_rest_days(raw_records, home_team, game_date)
        away_rest, away_b2b = compute_rest_days(raw_records, away_team, game_date)

        home_win_pct = compute_rolling_win_pct(raw_records, home_team, game_date)
        away_win_pct = compute_rolling_win_pct(raw_records, away_team, game_date)

        home_score = int(home.get("PTS", 0) or 0)
        away_score = int(away.get("PTS", 0) or 0)

        # Estimate ratings from box score
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
            "home_ortg": float(home.get("E_OFF_RATING", 110.0) or 110.0),
            "away_ortg": float(away.get("E_OFF_RATING", 110.0) or 110.0),
            "home_drtg": float(home.get("E_DEF_RATING", 110.0) or 110.0),
            "away_drtg": float(away.get("E_DEF_RATING", 110.0) or 110.0),
            "home_pace": home_pace,
            "away_pace": away_pace,
            "home_rest_days": home_rest,
            "away_rest_days": away_rest,
            "home_is_b2b": home_b2b,
            "away_is_b2b": away_b2b,
            "home_win_pct_prior": home_win_pct,
            "away_win_pct_prior": away_win_pct,
            "home_last_5_wins": int(home.get("L5_W", 2) or 2),
            "away_last_5_wins": int(away.get("L5_W", 2) or 2),
            "home_road_trip_game": 0,
            "away_road_trip_game": 0,
            "home_altitude_ft": TEAM_ALTITUDE_FT.get(home_team, 500),
            "away_altitude_ft": TEAM_ALTITUDE_FT.get(away_team, 500),
            "referee_crew_id": "",
            "predicted_home_wp": None,
            "actual_home_win": 1 if home_score > away_score else 0,
        })

    return structured

def structure_player_logs(raw_records: List[dict], season: str) -> List[dict]:
    """Structure raw player game logs into Epoch player log format."""
    structured = []
    for r in raw_records:
        try:
            pts = float(r.get("PTS", 0) or 0)
            ast = float(r.get("AST", 0) or 0)
            reb = float(r.get("REB", 0) or 0)
            fg3m = float(r.get("FG3M", 0) or 0)
            stl = float(r.get("STL", 0) or 0)
            blk = float(r.get("BLK", 0) or 0)
            mins = float(r.get("MIN", 0) or 0)
            usg = float(r.get("USG_PCT", 0.20) or 0.20)
            ts = float(r.get("TS_PCT", 0.55) or 0.55)
            pm = float(r.get("PLUS_MINUS", 0) or 0)
            matchup = r.get("MATCHUP", "")
            is_home = "vs." in matchup

            structured.append({
                "player_id": str(r.get("PLAYER_ID", "")),
                "player_name": r.get("PLAYER_NAME", ""),
                "team": r.get("TEAM_ABBREVIATION", ""),
                "game_id": str(r.get("GAME_ID", "")),
                "game_date": r.get("GAME_DATE", ""),
                "season": season,
                "points": pts,
                "assists": ast,
                "rebounds": reb,
                "threes_made": fg3m,
                "steals": stl,
                "blocks": blk,
                "minutes": mins,
                "usage_rate": usg,
                "true_shooting_pct": ts,
                "plus_minus": pm,
                "is_home": is_home,
                "rest_days": 2,
                "is_b2b": False,
                "night_type": None,
            })
        except Exception as e:
            continue
    return structured

def label_night_types(player_logs: List[dict]) -> List[dict]:
    """
    Label each player game log with a night type based on their
    personal performance distribution. Required by System 4.
    night_type: cold / below_avg / average / above_avg / hot
    """
    from collections import defaultdict
    player_points: Dict[str, List[float]] = defaultdict(list)
    for log in player_logs:
        player_points[log["player_id"]].append(log["points"])

    labeled = []
    for log in player_logs:
        pid = log["player_id"]
        pts = log["points"]
        history = player_points[pid]
        if len(history) < 5:
            log["night_type"] = "average"
            labeled.append(log)
            continue
        mean = np.mean(history)
        std = max(np.std(history), 1.0)
        z = (pts - mean) / std
        if z < -1.5:
            night_type = "cold"
        elif z < -0.5:
            night_type = "below_avg"
        elif z < 0.5:
            night_type = "average"
        elif z < 1.5:
            night_type = "above_avg"
        else:
            night_type = "hot"
        log["night_type"] = night_type
        labeled.append(log)
    return labeled

def run_real_data_pipeline(
    seasons: Optional[List[str]] = None,
    max_players: int = 150,
) -> dict:
    """
    Main entry point. Pull all real NBA data, structure it,
    and write to output files. Returns summary stats.
    """
    seasons = seasons or SEASONS_TO_PULL
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    all_game_logs = []
    all_player_logs = []

    for season in seasons:
        print(f"Pulling season {season}...")

        raw_team_logs = pull_team_game_logs(season)
        print(f"  Team records: {len(raw_team_logs)}")

        if raw_team_logs:
            game_logs = structure_game_logs(raw_team_logs, season)
            all_game_logs.extend(game_logs)
            print(f"  Structured games: {len(game_logs)}")

        raw_player_logs = pull_player_game_logs(season, max_players)
        print(f"  Player records: {len(raw_player_logs)}")

        if raw_player_logs:
            player_logs = structure_player_logs(raw_player_logs, season)
            all_player_logs.extend(player_logs)

    # Label night types
    all_player_logs = label_night_types(all_player_logs)

    # Write game logs
    with open(GAME_LOGS_PATH, "w") as f:
        for log in all_game_logs:
            f.write(json.dumps(log) + "\n")

    # Write player logs
    with open(PLAYER_LOGS_PATH, "w") as f:
        for log in all_player_logs:
            f.write(json.dumps(log) + "\n")

    # Extract injury games (rough proxy: games where team scored
    # significantly below their season average — real injury data
    # requires a separate injury report endpoint)
    injury_logs = _extract_injury_proxy_games(all_game_logs)
    with open(INJURY_LOGS_PATH, "w") as f:
        for log in injury_logs:
            f.write(json.dumps(log) + "\n")

    return {
        "seasons_pulled": seasons,
        "total_games": len(all_game_logs),
        "total_player_logs": len(all_player_logs),
        "injury_proxy_games": len(injury_logs),
        "output_files": [
            str(GAME_LOGS_PATH),
            str(PLAYER_LOGS_PATH),
            str(INJURY_LOGS_PATH),
        ],
    }

def _extract_injury_proxy_games(game_logs: List[dict]) -> List[dict]:
    """
    Proxy for injury games: identify games where a team scored
    significantly below their season average offensive rating.
    These are candidates for star-player-absent games.
    """
    from collections import defaultdict
    team_ortgs: Dict[str, List[float]] = defaultdict(list)
    for g in game_logs:
        team_ortgs[g["home_team"]].append(g["home_ortg"])
        team_ortgs[g["away_team"]].append(g["away_ortg"])

    team_avg_ortg = {t: np.mean(v) for t, v in team_ortgs.items() if v}
    team_std_ortg = {t: max(np.std(v), 1.0) for t, v in team_ortgs.items() if v}

    injury_proxies = []
    for g in game_logs:
        for side, team, ortg in [
            ("home", g["home_team"], g["home_ortg"]),
            ("away", g["away_team"], g["away_ortg"]),
        ]:
            avg = team_avg_ortg.get(team, 110.0)
            std = team_std_ortg.get(team, 5.0)
            z = (ortg - avg) / std
            if z < -1.5:  # >1.5 std below average → likely injury game
                injury_proxies.append({
                    "game_id": g["game_id"],
                    "game_date": g["game_date"],
                    "injured_team": team,
                    "injured_player": "UNKNOWN",
                    "injury_type": "proxy",
                    "player_usage_rate": 0.25,
                    "player_ortg_impact": z * std,
                    "team_ortg_before": avg,
                    "team_ortg_after": ortg,
                    "team_drtg_before": g[f"{side}_drtg"],
                    "team_drtg_after": g[f"{side}_drtg"],
                    "win_probability_delta": z * -0.05,
                    "actual_outcome": g[f"{'home' if side == 'home' else 'away'}_win"],
                })
    return injury_proxies

def load_game_logs() -> List[dict]:
    """Load structured game logs from disk."""
    if not GAME_LOGS_PATH.exists():
        return []
    logs = []
    with open(GAME_LOGS_PATH) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    logs.append(json.loads(line))
                except Exception:
                    continue
    return logs

def load_player_logs() -> List[dict]:
    """Load structured player logs from disk."""
    if not PLAYER_LOGS_PATH.exists():
        return []
    logs = []
    with open(PLAYER_LOGS_PATH) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    logs.append(json.loads(line))
                except Exception:
                    continue
    return logs

def load_injury_logs() -> List[dict]:
    """Load injury proxy game logs from disk."""
    if not INJURY_LOGS_PATH.exists():
        return []
    logs = []
    with open(INJURY_LOGS_PATH) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    logs.append(json.loads(line))
                except Exception:
                    continue
    return logs
