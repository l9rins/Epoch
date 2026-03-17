"""
ingest_injury_history.py — Epoch Engine
=========================================
Populates data/injury_game_logs.jsonl with real historical NBA injury data
so the ensemble can learn from actual "hampered player" game states.

Why this matters:
  The ensemble AUC is stuck at 0.621 because injury_impact_home/away (feature
  indices 39/40) are almost always 0.0 — the model never sees a non-zero
  injury signal during training. It learns to ignore those features entirely.
  This script fixes that by backfilling 5 seasons of real injury history.

Data sources (in priority order):
  1. nba_api PlayerGameLogs — detects injury games from anomalous stat lines
     (DNP records and sharp minute drops signal real injuries)
  2. Basketball Reference injury log scraper — HTML table at
     /friv/injuries.fcgi (historical, updated daily)
  3. Proxy detection — games where a team's ortg dropped >1.5 std below
     their rolling average (already in real_data_pipeline.py, reused here)

Output schema (one record per injured-player-game):
  {
    "game_id":              str,
    "game_date":            str (YYYY-MM-DD),
    "season":               str,
    "injured_team":         str (team abbreviation),
    "injured_player":       str,
    "player_id":            str,
    "injury_type":          str  (ankle/knee/shoulder/back/hamstring/hand/hip/illness/dnp/proxy),
    "severity":             str  (mild/moderate/severe/dnp),
    "position":             str  (PG/SG/SF/PF/C),
    "player_usage_rate":    float (0-1),
    "minutes_played":       float,
    "minutes_expected":     float,
    "minutes_delta_pct":    float (negative = played less than expected),
    "player_ortg_impact":   float,
    "win_probability_delta":float,
    "source":               str,
  }

Usage:
    python -m src.pipeline.ingest_injury_history
    python -m src.pipeline.ingest_injury_history --seasons 2 --dry-run
    python -m src.pipeline.ingest_injury_history --retrain-after
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import requests
from bs4 import BeautifulSoup

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("ingest_injury_history")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SEASONS = ["2020-21", "2021-22", "2022-23", "2023-24", "2024-25"]

OUTPUT_PATH = Path("data/injury_game_logs.jsonl")
PLAYER_LOGS_PATH = Path("data/player_game_logs.jsonl")
GAME_LOGS_PATH = Path("data/real_game_logs.jsonl")
CHECKPOINT_PATH = Path("data/.injury_checkpoint.json")
REPORT_PATH = Path("data/injury_ingestion_report.json")

# nba_api rate limiting
NBA_API_SLEEP = 2.2
BACKOFF_BASE = 2.0
BACKOFF_MAX = 60.0
MAX_RETRIES = 3

# Injury detection thresholds
DNP_MINUTES_THRESHOLD = 3.0        # below this = effectively DNP
SHARP_DROP_Z_THRESHOLD = -1.8      # z-score below this = injury-flagged
MIN_GAMES_FOR_BASELINE = 5         # need this many games to compute baseline
DEFAULT_USAGE_RATE = 0.22
ORTG_IMPACT_SCALE = 0.05           # per std deviation below average

# Basketball Reference
BBALL_REF_BASE = "https://www.basketball-reference.com"
BBALL_REF_INJURY_URL = f"{BBALL_REF_BASE}/friv/injuries.fcgi"
BBALL_REF_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
BBALL_REF_SLEEP = 6.0              # increased to be safer

# Injury keyword → type mapping for BBRef description parsing
INJURY_TYPE_KEYWORDS: dict[str, list[str]] = {
    "ankle":      ["ankle"],
    "knee":       ["knee", "acl", "mcl", "meniscus", "patella"],
    "shoulder":   ["shoulder", "rotator", "cuff", "labrum"],
    "back":       ["back", "lumbar", "spine", "vertebr"],
    "hamstring":  ["hamstring", "hammy"],
    "hand":       ["hand", "finger", "wrist", "thumb"],
    "hip":        ["hip", "groin", "adductor"],
    "illness":    ["illness", "sick", "flu", "covid", "personal", "non-covid"],
    "concussion": ["concussion", "head"],
    "foot":       ["foot", "heel", "achilles", "plantar"],
    "calf":       ["calf", "shin"],
}

# Severity keywords
SEVERITY_KEYWORDS: dict[str, list[str]] = {
    "severe":   ["acl", "torn", "fracture", "break", "broke", "surgery", "season"],
    "moderate": ["grade 2", "sprain", "strain", "questionable", "doubtful"],
    "mild":     ["grade 1", "soreness", "sore", "bruise", "contusion", "probable"],
}

# Position lookup by player role (approximate — would use roster data in prod)
POSITION_DEFAULTS: dict[str, str] = {
    "PG": "PG", "SG": "SG", "SF": "SF", "PF": "PF", "C": "C",
}

# Team abbreviation normalization (BBRef uses different abbrevs sometimes)
BBALL_REF_TEAM_MAP: dict[str, str] = {
    "CHO": "CHA", "NOH": "NOP", "NJN": "BKN", "SEA": "OKC",
    "GSW": "GSW", "PHO": "PHX", "BRK": "BKN", "SAS": "SAS",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    records = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return records


def _load_checkpoint() -> set[str]:
    if not CHECKPOINT_PATH.exists():
        return set()
    try:
        return set(json.loads(CHECKPOINT_PATH.read_text()))
    except Exception:
        return set()


def _save_checkpoint(completed: set[str]) -> None:
    CHECKPOINT_PATH.write_text(json.dumps(list(completed)))


def _normalize_team(abbr: str) -> str:
    return BBALL_REF_TEAM_MAP.get(abbr.upper(), abbr.upper())


def _parse_injury_type(description: str) -> str:
    desc_lower = description.lower()
    for injury_type, keywords in INJURY_TYPE_KEYWORDS.items():
        if any(kw in desc_lower for kw in keywords):
            return injury_type
    return "other"


def _parse_severity(description: str) -> str:
    desc_lower = description.lower()
    for severity, keywords in SEVERITY_KEYWORDS.items():
        if any(kw in desc_lower for kw in keywords):
            return severity
    return "moderate"  # default


def _sleep_with_jitter(base: float) -> None:
    import random
    time.sleep(base + random.uniform(0, 0.5))


# ---------------------------------------------------------------------------
# Source 1: DNP / sharp minute drop detection from player game logs
# ---------------------------------------------------------------------------

def detect_injury_games_from_player_logs(
    player_logs: list[dict],
    game_logs: list[dict],
) -> list[dict]:
    """
    Detect injury-affected games from player logs by finding:
    1. DNP records (minutes < DNP_MINUTES_THRESHOLD)
    2. Sharp minute drops (z-score below SHARP_DROP_Z_THRESHOLD)

    These are the most reliable injury proxies available without
    external injury report data.
    """
    # Build player minute baselines
    player_minutes: dict[str, list[float]] = defaultdict(list)
    player_games: dict[str, list[dict]] = defaultdict(list)

    for p_log in player_logs:
        pid = p_log.get("player_id", "")
        mins = float(p_log.get("minutes", 0))
        if mins > 0:
            player_minutes[pid].append(mins)
        player_games[pid].append(p_log)

    # Build game_id → game lookup
    game_lookup: dict[str, dict] = {g.get("game_id", ""): g for g in game_logs}

    # Build player usage rates
    player_usage: dict[str, float] = {}
    for pid, logs in player_games.items():
        usages = [float(l.get("usage_rate", DEFAULT_USAGE_RATE)) for l in logs]
        player_usage[pid] = float(np.mean(usages)) if usages else DEFAULT_USAGE_RATE

    injury_records = []
    processed_keys = set()

    for p_log in player_logs:
        pid = p_log.get("player_id", "")
        gid = p_log.get("game_id", "")
        key = f"{pid}_{gid}"

        if key in processed_keys:
            continue
        processed_keys.add(key)

        mins = float(p_log.get("minutes", 0))
        baseline = player_minutes.get(pid, [])

        if len(baseline) < MIN_GAMES_FOR_BASELINE:
            continue

        baseline_mean = float(np.mean(baseline))
        baseline_std = max(float(np.std(baseline)), 2.0)
        z = (mins - baseline_mean) / baseline_std

        is_dnp = mins < DNP_MINUTES_THRESHOLD
        is_sharp_drop = z < SHARP_DROP_Z_THRESHOLD

        if not (is_dnp or is_sharp_drop):
            continue

        game = game_lookup.get(gid, {})
        team = p_log.get("team", "")
        is_home = p_log.get("is_home", False)
        home_team = game.get("home_team", "")

        injured_team = team
        usage = player_usage.get(pid, DEFAULT_USAGE_RATE)

        # Estimate win probability delta
        # Usage × minutes_delta_pct × scale factor
        minutes_delta_pct = (mins - baseline_mean) / max(baseline_mean, 1.0)
        wp_delta = float(np.clip(minutes_delta_pct * usage * ORTG_IMPACT_SCALE, -0.15, 0.0))

        injury_records.append({
            "game_id": gid,
            "game_date": p_log.get("game_date", ""),
            "season": p_log.get("season", ""),
            "injured_team": injured_team,
            "injured_player": p_log.get("player_name", ""),
            "player_id": pid,
            "injury_type": "dnp" if is_dnp else "proxy",
            "severity": "severe" if is_dnp else ("moderate" if z < -2.5 else "mild"),
            "position": "SG",  # default — override with roster data if available
            "player_usage_rate": round(usage, 4),
            "minutes_played": mins,
            "minutes_expected": round(baseline_mean, 1),
            "minutes_delta_pct": round(minutes_delta_pct, 4),
            "player_ortg_impact": round(z * baseline_std * ORTG_IMPACT_SCALE, 4),
            "win_probability_delta": round(wp_delta, 4),
            "source": "player_log_detection",
        })

    log.info(
        "Player log detection: %d injury-flagged game records found",
        len(injury_records),
    )
    return injury_records


# ---------------------------------------------------------------------------
# Source 2: Basketball Reference injury log scraper
# ---------------------------------------------------------------------------

def scrape_bball_ref_injuries(season: str) -> list[dict]:
    """
    Scrape Basketball Reference's historical injury log for a season.
    URL: https://www.basketball-reference.com/friv/injuries.fcgi
    Note: BBRef only keeps current season injuries on this page.
    For historical, we scrape the per-season transaction logs.
    """
    # For historical seasons, BBRef stores injury transactions here:
    # /leagues/NBA_{YYYY}_transactions.html
    season_year = int(season[:4]) + 1  # "2023-24" → 2024
    url = f"{BBALL_REF_BASE}/leagues/NBA_{season_year}_transactions.html"

    log.info("Scraping BBRef transactions for %s: %s", season, url)
    _sleep_with_jitter(BBALL_REF_SLEEP)

    try:
        resp = requests.get(url, headers=BBALL_REF_HEADERS, timeout=20)
        resp.raise_for_status()
    except requests.RequestException as exc:
        log.warning("BBRef scrape failed for %s: %s", season, exc)
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    records = []

    # Find the transactions div
    content = soup.find("div", {"id": "content"})
    if not content:
        log.warning("No content div found on BBRef transactions page for %s", season)
        return []

    # Each transaction is a <p> element with date and description
    # Format: "Month DD, YYYY: Team — Player injured (description)"
    transaction_paras = content.find_all("p")
    date_pattern = re.compile(r"(\w+ \d+, \d{4})")
    injury_pattern = re.compile(
        r"([A-Z]{2,4})\s+placed\s+(.+?)\s+on\s+(injured|IL|inactive)",
        re.IGNORECASE,
    )

    current_date = None
    for p in transaction_paras:
        text = p.get_text(" ", strip=True)
        if not text:
            continue

        # Extract date
        date_match = date_pattern.search(text)
        if date_match:
            try:
                current_date = datetime.strptime(
                    date_match.group(1), "%B %d, %Y"
                ).strftime("%Y-%m-%d")
            except ValueError:
                pass

        # Check for injury placement
        if not current_date:
            continue

        inj_match = injury_pattern.search(text)
        if not inj_match:
            continue

        team_abbr = _normalize_team(inj_match.group(1))
        player_name = inj_match.group(2).strip()

        # Extract injury description (text after the player name)
        injury_desc = text[inj_match.end():].strip(" .,;:")
        injury_type = _parse_injury_type(injury_desc or text)
        severity = _parse_severity(injury_desc or text)

        records.append({
            "game_id": "",           # no game_id from transactions — matched by date
            "game_date": current_date,
            "season": season,
            "injured_team": team_abbr,
            "injured_player": player_name,
            "player_id": "",
            "injury_type": injury_type,
            "severity": severity,
            "position": "SG",        # unknown from transaction log
            "player_usage_rate": DEFAULT_USAGE_RATE,
            "minutes_played": 0.0,
            "minutes_expected": 0.0,
            "minutes_delta_pct": -1.0,  # placed on IL = out entirely
            "player_ortg_impact": round(-DEFAULT_USAGE_RATE * ORTG_IMPACT_SCALE * 20, 4),
            "win_probability_delta": round(-DEFAULT_USAGE_RATE * 0.10, 4),
            "source": "bball_ref_transactions",
        })

    log.info("BBRef transactions for %s: %d injury records", season, len(records))
    return records


def scrape_bball_ref_current_injuries() -> list[dict]:
    """
    Scrape the current season's injury report from BBRef (today's page).
    Useful for enriching games in the current season.
    """
    log.info("Scraping BBRef current injury report...")
    _sleep_with_jitter(BBALL_REF_SLEEP)

    try:
        resp = requests.get(BBALL_REF_INJURY_URL, headers=BBALL_REF_HEADERS, timeout=20)
        resp.raise_for_status()
    except requests.RequestException as exc:
        log.warning("BBRef current injuries scrape failed: %s", exc)
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    table = soup.find("table", {"id": "injuries"})
    if not table:
        log.warning("No injuries table found on BBRef injury page")
        return []

    records = []
    today = datetime.now().strftime("%Y-%m-%d")

    for row in table.find_all("tr")[1:]:  # skip header
        cells = row.find_all("td")
        if len(cells) < 4:
            continue

        player_name = cells[0].get_text(strip=True)
        team_abbr = _normalize_team(cells[1].get_text(strip=True))
        date_str = cells[2].get_text(strip=True)
            
        description = cells[3].get_text(strip=True) if len(cells) > 3 else ""

        injury_type = _parse_injury_type(description)
        severity = _parse_severity(description)

        try:
            game_date = datetime.strptime(date_str, "%b %d, %Y").strftime("%Y-%m-%d")
        except ValueError:
            game_date = today

        records.append({
            "game_id": "",
            "game_date": game_date,
            "season": "2024-25",
            "injured_team": team_abbr,
            "injured_player": player_name,
            "player_id": "",
            "injury_type": injury_type,
            "severity": severity,
            "position": "SG",
            "player_usage_rate": DEFAULT_USAGE_RATE,
            "minutes_played": 0.0,
            "minutes_expected": 0.0,
            "minutes_delta_pct": -1.0,
            "player_ortg_impact": round(-DEFAULT_USAGE_RATE * ORTG_IMPACT_SCALE * 20, 4),
            "win_probability_delta": round(-DEFAULT_USAGE_RATE * 0.10, 4),
            "source": "bball_ref_current",
        })

    log.info("BBRef current injuries: %d records", len(records))
    return records


# ---------------------------------------------------------------------------
# Source 3: Match injury records to game IDs
# ---------------------------------------------------------------------------

def match_injuries_to_games(
    injury_records: list[dict],
    game_logs: list[dict],
) -> list[dict]:
    """
    For injury records that have game_date but no game_id, find the
    nearest game played by that team on or after the injury date.
    Fills in game_id and win_probability_delta from actual game context.
    """
    # Build date → games lookup
    date_team_games: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for game in game_logs:
        date = game.get("game_date", "")
        home = game.get("home_team", "")
        away = game.get("away_team", "")
        date_team_games[(date, home)].append(game)
        date_team_games[(date, away)].append(game)

    matched = []
    unmatched = 0

    for rec in injury_records:
        if rec.get("game_id"):
            matched.append(rec)
            continue

        team = rec.get("injured_team", "")
        injury_date = rec.get("game_date", "")

        # Find the next game this team played on or after the injury date
        candidate_games = []
        for (date, t), games in date_team_games.items():
            if t == team and date >= injury_date:
                candidate_games.extend(games)

        if not candidate_games:
            unmatched += 1
            continue

        # Take the earliest game
        candidate_games.sort(key=lambda g: g.get("game_date", ""))
        target_game = candidate_games[0]
        gid = target_game.get("game_id", "")

        rec = {**rec, "game_id": gid, "game_date": target_game.get("game_date", rec["game_date"])}
        matched.append(rec)

    log.info(
        "Injury-to-game matching: %d matched, %d unmatched (no game found in logs)",
        len(matched), unmatched,
    )
    return matched


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

def deduplicate_injury_records(records: list[dict]) -> list[dict]:
    """
    Deduplicates by (game_id, player_id, injured_player).
    Prefers records with more specific injury_type (not 'proxy' or 'other').
    """
    seen: dict[str, dict] = {}

    priority_order = ["bball_ref_transactions", "bball_ref_current",
                      "player_log_detection", "proxy"]

    for rec in records:
        gid = rec.get("game_id", "")
        pid = rec.get("player_id", "") or rec.get("injured_player", "")
        key = f"{gid}_{pid}"

        if key not in seen:
            seen[key] = rec
        else:
            # Prefer higher-priority source
            existing_source = seen[key].get("source", "proxy")
            new_source = rec.get("source", "proxy")
            if priority_order.index(new_source) < priority_order.index(existing_source):
                seen[key] = rec
            # Also prefer non-proxy injury type
            elif seen[key].get("injury_type") in ("proxy", "other", "dnp"):
                if rec.get("injury_type") not in ("proxy", "other"):
                    seen[key] = rec

    deduped = list(seen.values())
    log.info("Deduplication: %d → %d records", len(records), len(deduped))
    return deduped


# ---------------------------------------------------------------------------
# Statistics report
# ---------------------------------------------------------------------------

def compute_injury_report(records: list[dict]) -> dict:
    if not records:
        return {"total": 0}

    by_type = defaultdict(int)
    by_severity = defaultdict(int)
    by_source = defaultdict(int)
    by_season = defaultdict(int)
    wp_deltas = []

    for r in records:
        by_type[r.get("injury_type", "unknown")] += 1
        by_severity[r.get("severity", "unknown")] += 1
        by_source[r.get("source", "unknown")] += 1
        by_season[r.get("season", "unknown")] += 1
        d = r.get("win_probability_delta", 0)
        if d != 0:
            wp_deltas.append(d)

    return {
        "total_records": len(records),
        "by_injury_type": dict(by_type),
        "by_severity": dict(by_severity),
        "by_source": dict(by_source),
        "by_season": dict(by_season),
        "avg_wp_delta": round(float(np.mean(wp_deltas)), 4) if wp_deltas else 0.0,
        "pct_with_game_id": round(
            sum(1 for r in records if r.get("game_id")) / len(records), 3
        ),
        "generated_at": datetime.now().isoformat(),
    }


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def run_injury_ingestion(
    seasons: list[str] | None = None,
    dry_run: bool = False,
) -> dict:
    target_seasons = seasons or SEASONS
    completed = _load_checkpoint()

    log.info("Loading existing game and player logs...")
    game_logs = _load_jsonl(GAME_LOGS_PATH)
    
    # Fallback: load from per-season files if consolidated log missing
    if not game_logs:
        log.info("Consolidated game log missing, loading from data/real/...")
        for path in sorted(Path("data/real").glob("games_*.jsonl")):
            game_logs.extend(_load_jsonl(path))
            
    player_logs = _load_jsonl(PLAYER_LOGS_PATH)

    if not game_logs:
        log.warning(
            "No game logs found at %s. Run real_data_pipeline first.", GAME_LOGS_PATH
        )

    all_injury_records: list[dict] = []

    # Source 1: detect from player log minute anomalies
    if player_logs:
        log.info("Running player log injury detection on %d player records...", len(player_logs))
        detected = detect_injury_games_from_player_logs(player_logs, game_logs)
        all_injury_records.extend(detected)
    else:
        log.warning(
            "No player logs found at %s. "
            "Run: python -m src.ml.real_data_pipeline (with player log support)",
            PLAYER_LOGS_PATH,
        )

    # Source 2: BBRef scraper per season
    for season in target_seasons:
        if season in completed:
            log.info("[%s] already scraped — skipping", season)
            continue

        log.info("[%s] scraping BBRef transaction log...", season)
        season_records = scrape_bball_ref_injuries(season)
        all_injury_records.extend(season_records)
        completed.add(season)
        _save_checkpoint(completed)

    # Source 2b: current season live injuries
    current_records = scrape_bball_ref_current_injuries()
    all_injury_records.extend(current_records)

    # Match injury records without game_id to nearest game
    if game_logs:
        log.info("Matching injury records to game IDs...")
        all_injury_records = match_injuries_to_games(all_injury_records, game_logs)

    # Deduplicate
    all_injury_records = deduplicate_injury_records(all_injury_records)

    # Report
    report = compute_injury_report(all_injury_records)
    log.info("Injury ingestion complete:")
    log.info("  Total records: %d", report["total_records"])
    log.info("  By type: %s", report["by_injury_type"])
    log.info("  By severity: %s", report["by_severity"])
    log.info("  Avg WP delta: %.4f", report["avg_wp_delta"])
    log.info("  %% with game_id: %.1f%%", report["pct_with_game_id"] * 100)

    if dry_run:
        log.info("Dry run — no files written")
        print(json.dumps(report, indent=2))
        return report

    # Append to existing injury_game_logs.jsonl (don't overwrite)
    existing = _load_jsonl(OUTPUT_PATH)
    existing_keys = {
        f"{r.get('game_id','')}_{r.get('player_id','') or r.get('injured_player','')}": True
        for r in existing
    }

    new_records = [
        r for r in all_injury_records
        if f"{r.get('game_id','')}_{r.get('player_id','') or r.get('injured_player','')}"
        not in existing_keys
    ]

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "a") as f:
        for r in new_records:
            f.write(json.dumps(r) + "\n")

    log.info(
        "Wrote %d new injury records to %s (%d already existed)",
        len(new_records), OUTPUT_PATH, len(existing),
    )

    report["new_records_written"] = len(new_records)
    report["existing_records"] = len(existing)
    REPORT_PATH.write_text(json.dumps(report, indent=2))

    return report


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Epoch Engine — Historical Injury Ingestion"
    )
    parser.add_argument(
        "--seasons", type=int, default=5,
        help="Number of most recent seasons to process (default: 5)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print report without writing any files",
    )
    parser.add_argument(
        "--retrain-after", action="store_true",
        help="After ingestion, run enrich_features.py to retrain ensemble",
    )
    parser.add_argument(
        "--clear-checkpoint", action="store_true",
        help="Clear checkpoint and re-scrape all seasons",
    )
    args = parser.parse_args()

    if args.clear_checkpoint and CHECKPOINT_PATH.exists():
        CHECKPOINT_PATH.unlink()
        log.info("Checkpoint cleared.")

    n = max(1, min(5, args.seasons))
    target_seasons = SEASONS[-n:]

    report = run_injury_ingestion(target_seasons, dry_run=args.dry_run)

    if args.retrain_after and not args.dry_run:
        log.info("Triggering feature enrichment and ensemble retrain...")
        import subprocess, sys
        result = subprocess.run(
            [sys.executable, "-m", "src.ml.enrich_features"],
            capture_output=False,
        )
        if result.returncode == 0:
            log.info("Ensemble retrain complete.")
        else:
            log.error("Ensemble retrain failed with code %d", result.returncode)

    return report


if __name__ == "__main__":
    main()
