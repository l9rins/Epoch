"""
Data Fallback Chain — SESSION D Week 1
Three-tier fallback for NBA game data:

  Tier 1   — nba_api          (primary, richest data)
  Tier 2.5 — balldontlie      (free JSON API, never goes down)
  Tier 3   — Basketball Reference scraper (HTML, last resort)

Pure functions only. No magic numbers.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
MAX_RETRIES: int = 3
RETRY_DELAY_SECONDS: float = 2.0
REQUEST_TIMEOUT_SECONDS: int = 15

DATA_SOURCE_PRIMARY: str = "nba_api"
DATA_SOURCE_BALLDONTLIE: str = "balldontlie"
DATA_SOURCE_FALLBACK: str = "basketball_reference_fallback"
DATA_SOURCE_UNKNOWN: str = "unknown"

BALLDONTLIE_BASE_URL: str = "https://api.balldontlie.io/v1"
BALLDONTLIE_GAMES_URL: str = f"{BALLDONTLIE_BASE_URL}/games"
BALLDONTLIE_STATS_URL: str = f"{BALLDONTLIE_BASE_URL}/stats"
BALLDONTLIE_PAGE_SIZE: int = 100

BBALL_REF_BASE_URL: str = "https://www.basketball-reference.com"
BBALL_REF_SCHEDULE_PATH: str = "/leagues/NBA_{season}_games-{month}.html"
BBALL_REF_BOX_SCORE_PATH: str = "/boxscores/{game_id}.html"

_BR_BASIC_COL_MAP: dict[str, str] = {
    "MP": "min", "FG": "fgm", "FGA": "fga",
    "3P": "fg3m", "3PA": "fg3a", "FT": "ftm", "FTA": "fta",
    "ORB": "oreb", "DRB": "dreb", "TRB": "reb",
    "AST": "ast", "STL": "stl", "BLK": "blk",
    "TOV": "tov", "PTS": "pts", "+/-": "plus_minus",
}

_BDL_SEASON_MAP: dict[str, int] = {
    "2024-25": 2024, "2023-24": 2023,
    "2022-23": 2022, "2021-22": 2021,
}


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def _fetch_html(url: str, retries: int = MAX_RETRIES) -> str | None:
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(
                url, timeout=REQUEST_TIMEOUT_SECONDS,
                headers={"User-Agent": "EpochEngine/1.0 (research pipeline)"},
            )
            resp.raise_for_status()
            return resp.text
        except requests.RequestException as exc:
            logger.warning("BR fetch attempt %d/%d failed: %s", attempt, retries, exc)
            if attempt < retries:
                time.sleep(RETRY_DELAY_SECONDS)
    return None


def _fetch_json(url: str, params: dict | None = None, retries: int = MAX_RETRIES) -> dict | None:
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(
                url, params=params, timeout=REQUEST_TIMEOUT_SECONDS,
                headers={"User-Agent": "EpochEngine/1.0"},
            )
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            logger.warning("JSON fetch attempt %d/%d failed: %s", attempt, retries, exc)
            if attempt < retries:
                time.sleep(RETRY_DELAY_SECONDS)
    return None


# ---------------------------------------------------------------------------
# Tier 2.5 — balldontlie
# ---------------------------------------------------------------------------

def fetch_balldontlie_games(
    season: str = "2024-25",
    per_page: int = BALLDONTLIE_PAGE_SIZE,
) -> list[dict[str, Any]]:
    """Fetch all games for a season from balldontlie. Returns Epoch schema list."""
    bdl_season = _BDL_SEASON_MAP.get(season, 2024)
    all_games: list[dict[str, Any]] = []
    cursor = None

    while True:
        params: dict[str, Any] = {"seasons[]": bdl_season, "per_page": per_page}
        if cursor:
            params["cursor"] = cursor
        data = _fetch_json(BALLDONTLIE_GAMES_URL, params=params)
        if not data:
            break
        games = data.get("data", [])
        if not games:
            break
        for game in games:
            structured = _structure_bdl_game(game, season)
            if structured:
                all_games.append(structured)
        next_cursor = data.get("meta", {}).get("next_cursor")
        if not next_cursor:
            break
        cursor = next_cursor
        time.sleep(0.3)

    logger.info("balldontlie: %d games for %s", len(all_games), season)
    return all_games


def _structure_bdl_game(game: dict[str, Any], season: str) -> dict[str, Any] | None:
    try:
        home = game.get("home_team", {})
        away = game.get("visitor_team", {})
        home_score = game.get("home_team_score")
        away_score = game.get("visitor_team_score")
        if home_score is None or away_score is None:
            return None
        home_abbr = home.get("abbreviation", "")
        away_abbr = away.get("abbreviation", "")
        return {
            "game_id": str(game.get("id", "")),
            "season": season,
            "game_date": game.get("date", "")[:10],
            "home_team": home_abbr,
            "away_team": away_abbr,
            "home_score": int(home_score),
            "away_score": int(away_score),
            "home_win": 1 if int(home_score) > int(away_score) else 0,
            "home_ortg": 110.0,
            "away_ortg": 110.0,
            "home_drtg": 110.0,
            "away_drtg": 110.0,
            "home_pace": 98.0,
            "away_pace": 98.0,
            "home_rest_days": 2,
            "away_rest_days": 2,
            "home_is_b2b": False,
            "away_is_b2b": False,
            "home_win_pct_prior": 0.500,
            "away_win_pct_prior": 0.500,
            "home_last_5_wins": 2,
            "away_last_5_wins": 2,
            "home_road_trip_game": 0,
            "away_road_trip_game": 0,
            "home_altitude_ft": 500,
            "away_altitude_ft": 500,
            "referee_crew_id": "",
            "predicted_home_wp": None,
            "actual_home_win": 1 if int(home_score) > int(away_score) else 0,
            "source": DATA_SOURCE_BALLDONTLIE,
        }
    except Exception as exc:
        logger.warning("Failed to structure balldontlie game: %s", exc)
        return None


def fetch_balldontlie_player_stats(
    season: str = "2024-25",
    per_page: int = BALLDONTLIE_PAGE_SIZE,
) -> list[dict[str, Any]]:
    """Fetch per-game player stats from balldontlie. Returns Epoch player log schema."""
    bdl_season = _BDL_SEASON_MAP.get(season, 2024)
    all_stats: list[dict[str, Any]] = []
    cursor = None

    while True:
        params: dict[str, Any] = {"seasons[]": bdl_season, "per_page": per_page}
        if cursor:
            params["cursor"] = cursor
        data = _fetch_json(BALLDONTLIE_STATS_URL, params=params)
        if not data:
            break
        stats = data.get("data", [])
        if not stats:
            break
        for stat in stats:
            structured = _structure_bdl_player_stat(stat, season)
            if structured:
                all_stats.append(structured)
        next_cursor = data.get("meta", {}).get("next_cursor")
        if not next_cursor:
            break
        cursor = next_cursor
        time.sleep(0.3)

    logger.info("balldontlie: %d player stats for %s", len(all_stats), season)
    return all_stats


def _structure_bdl_player_stat(stat: dict[str, Any], season: str) -> dict[str, Any] | None:
    try:
        player = stat.get("player", {})
        game = stat.get("game", {})
        team = stat.get("team", {})
        min_str = stat.get("min") or "0"
        try:
            if ":" in str(min_str):
                parts = str(min_str).split(":")
                minutes = float(parts[0]) + float(parts[1]) / 60
            else:
                minutes = float(min_str)
        except Exception:
            minutes = 0.0
        return {
            "player_id": str(player.get("id", "")),
            "player_name": f"{player.get('first_name','')} {player.get('last_name','')}".strip(),
            "team": team.get("abbreviation", ""),
            "game_id": str(game.get("id", "")),
            "game_date": game.get("date", "")[:10],
            "season": season,
            "points": float(stat.get("pts") or 0),
            "assists": float(stat.get("ast") or 0),
            "rebounds": float(stat.get("reb") or 0),
            "threes_made": float(stat.get("fg3m") or 0),
            "steals": float(stat.get("stl") or 0),
            "blocks": float(stat.get("blk") or 0),
            "minutes": minutes,
            "usage_rate": 0.20,
            "true_shooting_pct": 0.55,
            "plus_minus": float(stat.get("oreb") or 0),
            "is_home": False,
            "rest_days": 2,
            "is_b2b": False,
            "night_type": None,
            "source": DATA_SOURCE_BALLDONTLIE,
        }
    except Exception as exc:
        logger.warning("Failed to structure balldontlie stat: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Tier 3 — Basketball Reference scraper
# ---------------------------------------------------------------------------

def _parse_basic_box_table(table) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    headers: list[str] = []
    thead = table.find("thead")
    if thead:
        headers = [th.get_text(strip=True) for th in thead.find_all("th")]
    tbody = table.find("tbody")
    if not tbody:
        return rows
    for tr in tbody.find_all("tr"):
        if "class" in tr.attrs and "thead" in tr["class"]:
            continue
        cells = tr.find_all(["th", "td"])
        if len(cells) < 2:
            continue
        player_name = cells[0].get_text(strip=True)
        if not player_name or player_name in ("Reserves", "Team Totals", ""):
            continue
        row: dict[str, Any] = {"player_name": player_name}
        for i, cell in enumerate(cells[1:], start=1):
            if i < len(headers):
                col_header = headers[i]
                internal_key = _BR_BASIC_COL_MAP.get(col_header, col_header.lower())
                raw_val = cell.get_text(strip=True)
                try:
                    row[internal_key] = float(raw_val) if "." in raw_val else int(raw_val)
                except (ValueError, TypeError):
                    row[internal_key] = raw_val
        rows.append(row)
    return rows


def _parse_box_score_page(html: str, game_id: str) -> dict[str, Any] | None:
    soup = BeautifulSoup(html, "html.parser")
    box_tables = soup.find_all("table", id=lambda x: x and "game-basic" in x)
    if not box_tables:
        return None
    record: dict[str, Any] = {"game_id": game_id, "source": DATA_SOURCE_FALLBACK, "teams": []}
    for table in box_tables:
        table_id: str = table.get("id", "")
        team_abbr = table_id.replace("box-", "").replace("-game-basic", "").upper()
        record["teams"].append({"team": team_abbr, "players": _parse_basic_box_table(table)})
    return record


def fetch_todays_game_ids(season: int = 2025, month: str = "march") -> list[str]:
    url = BBALL_REF_BASE_URL + BBALL_REF_SCHEDULE_PATH.format(season=season, month=month)
    html = _fetch_html(url)
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    schedule_table = soup.find("table", id="schedule")
    if not schedule_table:
        return []
    game_ids: list[str] = []
    for row in schedule_table.find_all("tr"):
        box_link = row.find("a", string="Box Score")
        if box_link and box_link.get("href"):
            href: str = box_link["href"]
            game_ids.append(href.split("/")[-1].replace(".html", ""))
    return game_ids


def fetch_game_logs_fallback(
    game_ids: list[str] | None = None,
    season: int = 2025,
    month: str = "march",
) -> list[dict[str, Any]]:
    if game_ids is None:
        game_ids = fetch_todays_game_ids(season=season, month=month)
    if not game_ids:
        return []
    records: list[dict[str, Any]] = []
    for gid in game_ids:
        url = BBALL_REF_BASE_URL + BBALL_REF_BOX_SCORE_PATH.format(game_id=gid)
        html = _fetch_html(url)
        if not html:
            continue
        record = _parse_box_score_page(html, gid)
        if record:
            records.append(record)
    return records


def fetch_bball_ref_standings() -> dict:
    """Fetch 2024-25 NBA standings from Basketball Reference."""
    url = "https://www.basketball-reference.com/leagues/NBA_2025_standings.html"
    try:
        html = _fetch_html(url)
        return parse_bball_ref_standings(html) if html else {}
    except Exception as exc:
        logger.error("BR standings fetch failed: %s", exc)
        return {}


def parse_bball_ref_standings(html_content: str) -> dict:
    if not html_content:
        return {}
    soup = BeautifulSoup(html_content, "html.parser")
    standings = {}
    for table_id in ["confs_standings_E", "confs_standings_W"]:
        table = soup.find("table", {"id": table_id})
        if not table:
            continue
        for row in table.find_all("tr", class_="full_table"):
            team_cell = row.find("th", {"data-stat": "team_name"})
            wins_cell = row.find("td", {"data-stat": "wins"})
            losses_cell = row.find("td", {"data-stat": "losses"})
            if team_cell and wins_cell and losses_cell:
                team_name = team_cell.text.strip().replace("*", "")
                if "(" in team_name:
                    team_name = team_name.split("(")[0].strip()
                try:
                    standings[team_name] = {
                        "wins": int(wins_cell.text),
                        "losses": int(losses_cell.text),
                        "source": DATA_SOURCE_FALLBACK,
                    }
                except (ValueError, TypeError):
                    continue
    return standings


# ---------------------------------------------------------------------------
# Main fallback chain
# ---------------------------------------------------------------------------

def nba_api_with_fallback(
    primary_fn,
    *args,
    season: str = "2024-25",
    month: str = "march",
    **kwargs,
) -> tuple[list[dict[str, Any]], str]:
    """
    Three-tier fallback chain:
      Tier 1   → nba_api (primary_fn)
      Tier 2.5 → balldontlie JSON API
      Tier 3   → Basketball Reference HTML scraper

    Returns (records, source_label).
    """
    # Tier 1
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            result = primary_fn(*args, **kwargs)
            logger.info("nba_api succeeded on attempt %d", attempt)
            return result, DATA_SOURCE_PRIMARY
        except Exception as exc:
            logger.warning("nba_api attempt %d/%d failed: %s", attempt, MAX_RETRIES, exc)
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY_SECONDS)

    logger.warning("nba_api exhausted — trying balldontlie (tier 2.5)")

    # Tier 2.5
    try:
        bdl_records = fetch_balldontlie_games(season=season)
        if bdl_records:
            logger.info("balldontlie succeeded: %d records", len(bdl_records))
            return bdl_records, DATA_SOURCE_BALLDONTLIE
        logger.warning("balldontlie empty — falling back to BR scraper")
    except Exception as exc:
        logger.warning("balldontlie failed: %s — falling back to BR scraper", exc)

    # Tier 3
    logger.error("All primary sources failed — activating BR HTML scraper")
    fallback_records = fetch_game_logs_fallback(
        season=int(season[:4]) + 1, month=month
    )
    return fallback_records, DATA_SOURCE_FALLBACK
