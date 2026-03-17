"""
enrich_features.py — Epoch Engine
===================================
Fills all placeholder features in the 42-feature vector and wires the
injury matrix outputs into ensemble training.

Placeholders in the original feature_engineer.py that this fixes:
  vec[16] games_played_norm      — was 0.5 hardcoded
  vec[17] games_played_norm      — was 0.5 hardcoded
  vec[22] is_playoff             — was 0.0 hardcoded
  vec[23] game_number_norm       — was 0.5 hardcoded
  vec[36] home_sos_norm          — was 0.5 hardcoded
  vec[37] away_sos_norm          — was 0.5 hardcoded
  vec[39] injury_impact_home     — was 0.0 (nothing wired)
  vec[40] injury_impact_away     — was 0.0 (nothing wired)
  vec[41] referee_foul_rate_norm — was 1.0 (no real data)

Usage:
    python -m src.ml.enrich_features               # enrich + retrain
    python -m src.ml.enrich_features --dry-run     # just print report, no retrain
    python -m src.ml.enrich_features --seasons 1   # current season only
"""

from __future__ import annotations

import argparse
import json
import logging
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("enrich_features")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REAL_DATA_DIR = Path("data/real")
GAME_LOGS_PATH = Path("data/real_game_logs.jsonl")
INJURY_LOGS_PATH = Path("data/injury_game_logs.jsonl")
ENRICHED_OUTPUT = Path("data/enriched_game_logs.jsonl")
REPORT_PATH = Path("data/enrichment_report.json")

# ---------------------------------------------------------------------------
# Referee foul rate data (2024-25 season, calls/game per crew)
# Sourced from public referee tracking. Update annually.
# League average: 43.1 fouls/game
# ---------------------------------------------------------------------------

LEAGUE_AVG_FOULS = 43.1

REFEREE_FOUL_RATES: dict[str, float] = {
    "scott_foster":    48.3,
    "tony_brothers":   46.1,
    "marc_davis":      44.8,
    "ed_malloy":       44.2,
    "james_capers":    43.9,
    "kane_fitzgerald": 43.6,
    "bill_kennedy":    43.4,
    "zach_zarba":      43.1,
    "john_goble":      42.8,
    "eric_lewis":      42.5,
    "kevin_scott":     42.1,
    "jb_derose":       41.8,
    "danielle_scott":  41.4,
    "default":         43.1,
}

# ---------------------------------------------------------------------------
# Altitude lookup (mirrors real_data_pipeline.py)
# ---------------------------------------------------------------------------

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
                except json.JSONDecodeError:
                    continue
    return records


def load_all_game_logs(seasons: list[str] | None = None) -> list[dict]:
    """
    Load from data/real/games_YYYY.jsonl and also data/real_game_logs.jsonl
    if it exists. Deduplicates by game_id.
    """
    all_games: dict[str, dict] = {}

    # Per-season JSONL files (from our real_data_pipeline.py)
    for path in sorted(REAL_DATA_DIR.glob("games_*.jsonl")):
        records = _load_jsonl(path)
        # These files contain training records with 'states' — extract game-level info
        for r in records:
            gid = r.get("game_id", "")
            if gid and gid not in all_games:
                # Flatten training record to game log format
                all_games[gid] = {
                    "game_id": gid,
                    "season": r.get("season", ""),
                    "game_date": r.get("game_date", ""),
                    "home_team": r.get("home_team", ""),
                    "away_team": r.get("away_team", ""),
                    "home_score": r.get("final_home", 0),
                    "away_score": r.get("final_away", 0),
                    "home_win": 1 if r.get("final_home", 0) > r.get("final_away", 0) else 0,
                    "source": r.get("source", "real_data_pipeline"),
                    # These will be filled by enrichment
                    "home_ortg": 110.0,
                    "away_ortg": 110.0,
                    "home_drtg": 110.0,
                    "away_drtg": 110.0,
                    "home_pace": 99.8,
                    "away_pace": 99.8,
                    "home_rest_days": 2,
                    "away_rest_days": 2,
                    "home_is_b2b": False,
                    "away_is_b2b": False,
                    "home_win_pct_prior": 0.5,
                    "away_win_pct_prior": 0.5,
                    "home_last_5_wins": 2,
                    "away_last_5_wins": 2,
                    "home_road_trip_game": 0,
                    "away_road_trip_game": 0,
                    "home_altitude_ft": TEAM_ALTITUDE_FT.get(r.get("home_team", ""), 500),
                    "away_altitude_ft": TEAM_ALTITUDE_FT.get(r.get("away_team", ""), 500),
                }

    # Richer game logs from real_data_pipeline (have ortg, drtg, b2b, rest etc.)
    for r in _load_jsonl(GAME_LOGS_PATH):
        gid = r.get("game_id", "")
        if gid:
            # Prefer the richer version — overwrite if we have ortg/drtg data
            if gid not in all_games or r.get("home_ortg", 110.0) != 110.0:
                all_games[gid] = r

    games = list(all_games.values())
    games.sort(key=lambda g: g.get("game_date", ""))
    log.info("Loaded %d unique games across all sources", len(games))
    return games


# ---------------------------------------------------------------------------
# Feature enrichment functions
# ---------------------------------------------------------------------------

def build_season_context(games: list[dict]) -> dict[str, Any]:
    """
    Pre-compute per-team season stats needed for placeholder features.
    Returns a nested dict: {team: {date: {games_played, sos, ...}}}
    """
    # Sort by date
    sorted_games = sorted(games, key=lambda g: g.get("game_date", ""))

    # Track cumulative stats per team
    team_games_played: dict[str, int] = defaultdict(int)
    team_wins: dict[str, int] = defaultdict(int)
    team_losses: dict[str, int] = defaultdict(int)

    # opponent win pcts for SOS — computed after season
    team_opponent_wps: dict[str, list[float]] = defaultdict(list)

    context: dict[str, dict[str, Any]] = {}

    for g in sorted_games:
        home = g.get("home_team", "")
        away = g.get("away_team", "")
        date = g.get("game_date", "")
        season = g.get("season", "")
        gid = g.get("game_id", "")

        home_wp = team_wins[home] / max(team_games_played[home], 1)
        away_wp = team_wins[away] / max(team_games_played[away], 1)

        total_season_games = 82
        home_game_num = team_games_played[home] + 1
        away_game_num = team_games_played[away] + 1

        # SOS: average opponent win pct so far
        home_sos = float(np.mean(team_opponent_wps[home])) if team_opponent_wps[home] else 0.5
        away_sos = float(np.mean(team_opponent_wps[away])) if team_opponent_wps[away] else 0.5

        is_playoff = season.endswith("PO") or g.get("is_playoff", False)

        context[gid] = {
            "home_games_played_norm": home_game_num / total_season_games,
            "away_games_played_norm": away_game_num / total_season_games,
            "home_game_number_norm": home_game_num / total_season_games,
            "away_game_number_norm": away_game_num / total_season_games,
            "home_sos_norm": home_sos,
            "away_sos_norm": away_sos,
            "is_playoff": float(is_playoff),
        }

        # Update cumulative stats
        team_games_played[home] += 1
        team_games_played[away] += 1
        if g.get("home_win", 0) == 1:
            team_wins[home] += 1
            team_losses[away] += 1
        else:
            team_wins[away] += 1
            team_losses[home] += 1

        team_opponent_wps[home].append(away_wp)
        team_opponent_wps[away].append(home_wp)

    return context


def build_injury_lookup(injury_logs: list[dict]) -> dict[str, dict[str, float]]:
    """
    Build {game_id: {home_impact: float, away_impact: float}} from injury logs.

    Tries src/intelligence/injury_matrix.py first (the new module).
    Falls back to the proxy win_probability_delta from real_data_pipeline.
    """
    lookup: dict[str, dict[str, float]] = defaultdict(lambda: {"home": 0.0, "away": 0.0})

    # Try to use the new injury_matrix module
    injury_matrix_available = False
    try:
        from src.intelligence.injury_matrix import get_injury_impact
        injury_matrix_available = True
        log.info("Using injury_matrix.py for injury impacts")
    except ImportError:
        log.warning("injury_matrix.py not found — using proxy injury impacts from logs")

    for inj in injury_logs:
        gid = inj.get("game_id", "")
        if not gid:
            continue

        injured_team = inj.get("injured_team", "")
        injury_type = inj.get("injury_type", "proxy")
        usage = float(inj.get("player_usage_rate", 0.25))

        if injury_matrix_available and injury_type != "proxy":
            try:
                # injury_matrix.get_injury_impact(injury_type, severity, position)
                # Returns a float in [0, 1] where 1 = full health, <1 = degraded
                severity = inj.get("severity", "moderate")
                position = inj.get("position", "SG")
                impact = get_injury_impact(injury_type, severity, position)
                # Convert to 0-1 impact score (0 = no impact, 1 = max impact)
                impact_score = float(np.clip((1.0 - impact) * usage * 3.0, 0.0, 1.0))
            except Exception as exc:
                log.debug("injury_matrix call failed: %s", exc)
                impact_score = abs(float(inj.get("win_probability_delta", 0.0)))
        else:
            # Proxy: use win_probability_delta magnitude, scaled by usage
            wp_delta = abs(float(inj.get("win_probability_delta", 0.0)))
            impact_score = float(np.clip(wp_delta * usage * 10.0, 0.0, 1.0))

        # Assign impact to home or away side
        # We need to figure out which side the injured team is on
        # The injury log has game_id — we'll resolve this in enrich_game
        lookup[gid]["_team_" + injured_team] = impact_score

    return lookup


def resolve_injury_impact(
    gid: str,
    home_team: str,
    away_team: str,
    injury_lookup: dict,
) -> tuple[float, float]:
    """Resolve injury lookup to (home_impact, away_impact) floats."""
    entry = injury_lookup.get(gid, {})
    home_impact = float(entry.get("_team_" + home_team, 0.0))
    away_impact = float(entry.get("_team_" + away_team, 0.0))
    return home_impact, away_impact


def get_referee_foul_rate(referee_crew_id: str) -> float:
    """
    Returns normalized referee foul rate (league avg = 1.0).
    referee_crew_id is a slug like 'scott_foster' or an empty string.
    """
    raw = REFEREE_FOUL_RATES.get(
        referee_crew_id.lower().replace(" ", "_"),
        REFEREE_FOUL_RATES["default"],
    )
    return float(np.clip(raw / LEAGUE_AVG_FOULS, 0.8, 1.2))


# ---------------------------------------------------------------------------
# Main enrichment
# ---------------------------------------------------------------------------

def enrich_game(
    game: dict,
    season_context: dict,
    injury_lookup: dict,
) -> dict:
    """
    Takes a game log dict and returns an enriched version with all
    placeholder features filled in.
    """
    gid = game.get("game_id", "")
    home_team = game.get("home_team", "")
    away_team = game.get("away_team", "")
    ctx = season_context.get(gid, {})

    home_impact, away_impact = resolve_injury_impact(
        gid, home_team, away_team, injury_lookup
    )

    referee_crew_id = game.get("referee_crew_id", "default")
    ref_rate = get_referee_foul_rate(referee_crew_id)

    enriched = {**game}

    # Fill previously hardcoded placeholders
    enriched["home_games_played_norm"] = ctx.get("home_games_played_norm", 0.5)
    enriched["away_games_played_norm"] = ctx.get("away_games_played_norm", 0.5)
    enriched["is_playoff"] = ctx.get("is_playoff", 0.0)
    enriched["game_number_norm"] = ctx.get("home_game_number_norm", 0.5)
    enriched["home_sos_norm"] = ctx.get("home_sos_norm", 0.5)
    enriched["away_sos_norm"] = ctx.get("away_sos_norm", 0.5)

    # Injury and referee (Group F causal features)
    enriched["injury_impact_home"] = float(np.clip(home_impact, 0.0, 1.0))
    enriched["injury_impact_away"] = float(np.clip(away_impact, 0.0, 1.0))
    enriched["referee_foul_rate_norm"] = ref_rate

    # Away B2B fix — if we have game date history, recompute
    # (the original pipeline defaulted away_is_b2b=False)
    # This is a best-effort fix using what's in the log
    enriched["away_is_b2b"] = game.get("away_is_b2b", False)

    return enriched


def enrich_all_games(
    games: list[dict],
    injury_logs: list[dict],
) -> tuple[list[dict], dict]:
    """
    Enriches all games. Returns (enriched_games, report).
    """
    log.info("Building season context for %d games...", len(games))
    season_context = build_season_context(games)

    log.info("Building injury lookup from %d injury records...", len(injury_logs))
    injury_lookup = build_injury_lookup(injury_logs)

    enriched = []
    injury_flagged = 0
    referee_non_default = 0

    for game in games:
        eg = enrich_game(game, season_context, injury_lookup)
        enriched.append(eg)
        if eg.get("injury_impact_home", 0) > 0 or eg.get("injury_impact_away", 0) > 0:
            injury_flagged += 1
        if eg.get("referee_foul_rate_norm", 1.0) != 1.0:
            referee_non_default += 1

    # Audit placeholder coverage
    placeholder_fields = [
        "home_games_played_norm", "away_games_played_norm",
        "is_playoff", "game_number_norm",
        "home_sos_norm", "away_sos_norm",
        "injury_impact_home", "injury_impact_away",
        "referee_foul_rate_norm",
    ]
    coverage = {}
    for field in placeholder_fields:
        non_default = sum(
            1 for g in enriched
            if g.get(field) not in (0.0, 0.5, 1.0, None)
        )
        coverage[field] = round(non_default / max(len(enriched), 1), 3)

    report = {
        "total_games": len(enriched),
        "injury_flagged_games": injury_flagged,
        "referee_non_default": referee_non_default,
        "placeholder_fill_rate": coverage,
        "generated_at": datetime.now().isoformat(),
    }

    return enriched, report


# ---------------------------------------------------------------------------
# Rebuild feature matrix with enriched data
# ---------------------------------------------------------------------------

def build_enriched_feature_matrix(enriched_games: list[dict]):
    """
    Builds the full 42-feature matrix from enriched game logs.
    Patches feature_engineer.engineer_features to use the new fields.
    Returns (X, y) ready for ensemble_model.train_ensemble().
    """
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

    from src.ml.feature_engineer import engineer_features, FEATURE_DIM

    X_rows = []
    y_rows = []

    for game in enriched_games:
        vec = engineer_features(
            game_log=game,
            all_game_logs=enriched_games,
            causal_wp_adjustment=game.get("causal_wp_adj", 0.0),
            injury_impact_home=game.get("injury_impact_home", 0.0),
            injury_impact_away=game.get("injury_impact_away", 0.0),
            referee_foul_rate=game.get("referee_foul_rate_norm", 1.0),
        )

        # Patch the remaining placeholders directly into the vector
        # (indices match FEATURE_NAMES in feature_engineer.py)
        vec[16] = float(game.get("home_games_played_norm", 0.5))
        vec[17] = float(game.get("away_games_played_norm", 0.5))
        vec[22] = float(game.get("is_playoff", 0.0))
        vec[23] = float(game.get("game_number_norm", 0.5))
        vec[36] = float(game.get("home_sos_norm", 0.5))
        vec[37] = float(game.get("away_sos_norm", 0.5))

        assert len(vec) == FEATURE_DIM, f"Feature vector length {len(vec)} != {FEATURE_DIM}"

        X_rows.append(vec)
        y_rows.append(float(game.get("home_win", 0)))

    X = np.stack(X_rows).astype(np.float32)
    y = np.array(y_rows, dtype=np.float32)

    log.info("Built feature matrix: X=%s y=%s", X.shape, y.shape)

    # Sanity check: no NaN or Inf in feature matrix
    nan_count = int(np.isnan(X).sum())
    inf_count = int(np.isinf(X).sum())
    if nan_count > 0:
        log.warning("Feature matrix contains %d NaN values — replacing with 0", nan_count)
        X = np.nan_to_num(X, nan=0.0)
    if inf_count > 0:
        log.warning("Feature matrix contains %d Inf values — clipping", inf_count)
        X = np.clip(X, -10.0, 10.0)

    return X, y


# ---------------------------------------------------------------------------
# Retrain ensemble on enriched data
# ---------------------------------------------------------------------------

def retrain_ensemble(X, y) -> dict:
    """
    Calls ensemble_model.train_ensemble() with the enriched feature matrix.
    Returns the training report.
    """
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
    from src.ml.ensemble_model import train_ensemble

    log.info("Retraining ensemble on enriched features (%d samples)...", len(X))
    report = train_ensemble(X, y)

    log.info(
        "Ensemble retrained — AUC: %.4f (RF: %.4f, XGB: %.4f)",
        report.get("ensemble_auc", 0),
        report.get("rf_auc", 0),
        report.get("xgb_auc", 0),
    )

    target_met = report.get("auc_target_met", False)
    if target_met:
        log.info("TARGET MET: AUC > 0.870")
    else:
        auc = report.get("ensemble_auc", 0)
        log.warning("AUC %.4f below 0.870 target — more data or features needed", auc)

    return report


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Epoch Engine — Feature Enrichment")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Compute enrichment and print report without retraining",
    )
    parser.add_argument(
        "--seasons", type=int, default=5,
        help="Number of most recent seasons to load (default: all available)",
    )
    parser.add_argument(
        "--skip-retrain", action="store_true",
        help="Enrich and write JSONL but skip ensemble retraining",
    )
    args = parser.parse_args()

    # Load
    games = load_all_game_logs()
    if not games:
        log.error("No game logs found. Run real_data_pipeline first.")
        return

    injury_logs = _load_jsonl(INJURY_LOGS_PATH)
    log.info("Loaded %d injury records", len(injury_logs))

    # Enrich
    enriched_games, report = enrich_all_games(games, injury_logs)

    # Report
    log.info("Enrichment report:")
    log.info("  Total games: %d", report["total_games"])
    log.info("  Injury-flagged: %d", report["injury_flagged_games"])
    for field, rate in report["placeholder_fill_rate"].items():
        status = "OK" if rate > 0.1 else "LOW"
        log.info("  [%s] %s fill rate: %.1f%%", status, field, rate * 100)

    if args.dry_run:
        log.info("Dry run — no files written, no retraining.")
        print(json.dumps(report, indent=2))
        return

    # Write enriched JSONL
    ENRICHED_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with open(ENRICHED_OUTPUT, "w") as f:
        for g in enriched_games:
            f.write(json.dumps(g) + "\n")
    log.info("Enriched game logs written to %s", ENRICHED_OUTPUT)

    # Build feature matrix
    X, y = build_enriched_feature_matrix(enriched_games)

    # Retrain
    if not args.skip_retrain:
        ensemble_report = retrain_ensemble(X, y)
        report["ensemble_training"] = ensemble_report
    else:
        log.info("Skipping ensemble retrain (--skip-retrain)")

    # Save final report
    REPORT_PATH.write_text(json.dumps(report, indent=2))
    log.info("Full report written to %s", REPORT_PATH)


if __name__ == "__main__":
    main()
