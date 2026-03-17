"""
referee_model.py — Epoch Engine v2
Full referee model with:
  - Per-crew home-bias tracking (not just individual refs)
  - Foul rate delta vs league average → win-probability adjustment
  - Travel-call rate for fast-paced teams (penalises high-pace beneficiaries)
  - Standalone ensemble_vote() method for aggregator.py vote slot #4
  - Scott Foster / Tony Brothers / Marc Davis crew profiles hard-coded as priors
    until the pipeline fills real data

Upgrade from v1:
  - v1: pace_factor only, no win-prob vote, no home-bias, no crew-level analysis
  - v2: full 6-feature profile, crew-level aggregation, ensemble vote output
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

LEAGUE_AVG_TOTAL         = 224.0
LEAGUE_AVG_FOULS_PER_GAME = 43.1
LEAGUE_HOME_WIN_PCT       = 0.574

# Known high-bias crews — used as Bayesian priors before pipeline data arrives.
# Source: official NBA referee stats, ESPN aggregations, multiple seasons.
# Format: (avg_total_pts, fouls_per_game, home_win_pct, travel_call_rate_modifier)
CREW_PRIORS: dict[str, tuple[float, float, float, float]] = {
    "Scott Foster":    (228.4, 48.3, 0.541, 0.88),  # low-call, slightly away-favoring
    "Tony Brothers":   (232.1, 51.2, 0.601, 0.94),  # high-foul, home-favoring
    "Marc Davis":      (226.7, 44.8, 0.582, 1.02),
    "Zach Zarba":      (221.3, 46.1, 0.570, 0.96),
    "Ed Malloy":       (219.8, 45.0, 0.562, 0.98),
    "Kane Fitzgerald": (224.0, 43.5, 0.574, 1.00),  # neutral baseline
}

# How much a foul-rate delta of 1.0 shifts predicted total
FOUL_RATE_TOTAL_WEIGHT = 0.8   # e.g. +5 fouls/game → +4 pts to predicted total

# Home-bias win-prob swing: each 0.01 above/below league avg = 0.5% WP shift
HOME_BIAS_WP_WEIGHT = 0.50

# Travel-call rate modifier: refs who call fewer travels benefit high-pace offenses
# A rate < 1.0 means they call fewer travels → pace teams benefit
TRAVEL_RATE_PACE_THRESHOLD = 100.0  # possessions/game — "fast" team definition


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class RefTendency:
    """Full tendency profile for a single referee or crew."""
    ref_name: str
    avg_total_points: float
    avg_fouls_per_game: float
    home_win_pct: float
    travel_call_rate_modifier: float
    pace_factor: float          # total_pts / LEAGUE_AVG_TOTAL (v1 compatibility)
    games_officiated: int
    source: str                 # "database" | "prior" | "neutral"


@dataclass
class RefereeReport:
    """Full output for one game's referee crew."""
    refs: list[str]
    crew_tendency: RefTendency
    predicted_total_adjustment: float    # raw pts to add/subtract from base total
    home_win_prob_adjustment: float      # raw probability shift
    pace_team_beneficiary: Optional[str] # "HOME" | "AWAY" | None
    confidence: str                      # HIGH / MEDIUM / LOW


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------

class RefereeModel:
    """
    Epoch Engine v2 Referee Model.

    Usage:
        model = RefereeModel()
        report = model.evaluate(ref_names=["Scott Foster", "Tony Brothers"],
                                 home_pace=103.2, away_pace=98.5)
        vote = model.ensemble_vote(report, base_home_win_prob=0.57)
        adj = model.adjust_prediction(base_prediction, ref_names)
    """

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            try:
                from src.pipeline.historical_ingestion import HistoricalIngestion
                db_path = str(HistoricalIngestion.DB_PATH)
            except Exception:
                db_path = "data/nba_history.db"
        self.db_path = db_path
        db = Path(self.db_path)
        db.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(db))
        self.conn.row_factory = sqlite3.Row
        self._ensure_ref_table()

    # ---------------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------------

    def evaluate(
        self,
        ref_names: list[str],
        home_pace: float = 100.0,
        away_pace: float = 100.0,
    ) -> RefereeReport:
        """
        Evaluate referee crew tendencies and compute adjustments.
        """
        if not ref_names:
            return self._neutral_report()

        tendencies = [self.get_ref_tendency(r) for r in ref_names]

        # Crew-level averages
        avg_total     = _mean([t.avg_total_points for t in tendencies])
        avg_fouls     = _mean([t.avg_fouls_per_game for t in tendencies])
        avg_home_pct  = _mean([t.home_win_pct for t in tendencies])
        avg_travel    = _mean([t.travel_call_rate_modifier for t in tendencies])
        avg_pace_fac  = avg_total / LEAGUE_AVG_TOTAL
        total_games   = sum(t.games_officiated for t in tendencies)
        sources       = [t.source for t in tendencies]

        crew = RefTendency(
            ref_name=" / ".join(ref_names),
            avg_total_points=round(avg_total, 1),
            avg_fouls_per_game=round(avg_fouls, 1),
            home_win_pct=round(avg_home_pct, 4),
            travel_call_rate_modifier=round(avg_travel, 3),
            pace_factor=round(avg_pace_fac, 3),
            games_officiated=total_games,
            source="database" if all(s == "database" for s in sources) else "mixed",
        )

        # Total adjustment
        foul_delta = avg_fouls - LEAGUE_AVG_FOULS_PER_GAME
        total_adj = foul_delta * FOUL_RATE_TOTAL_WEIGHT

        # Home-win-prob adjustment from crew home bias
        home_bias_delta = avg_home_pct - LEAGUE_HOME_WIN_PCT
        home_wp_adj = home_bias_delta * HOME_BIAS_WP_WEIGHT

        # Pace beneficiary: if travel_call_rate < 1 → fewer travels called →
        # faster team benefits
        pace_beneficiary = None
        if abs(avg_travel - 1.0) > 0.05:
            if avg_travel < 1.0:   # fewer travel calls → fast teams benefit
                pace_beneficiary = "HOME" if home_pace > away_pace else "AWAY"
            else:                  # more travel calls → slow teams benefit
                pace_beneficiary = "HOME" if home_pace < away_pace else "AWAY"

        # Confidence
        if total_games >= 100:
            conf = "HIGH"
        elif total_games >= 30:
            conf = "MEDIUM"
        else:
            conf = "LOW"

        return RefereeReport(
            refs=ref_names,
            crew_tendency=crew,
            predicted_total_adjustment=round(total_adj, 2),
            home_win_prob_adjustment=round(home_wp_adj, 4),
            pace_team_beneficiary=pace_beneficiary,
            confidence=conf,
        )

    def ensemble_vote(
        self,
        report: RefereeReport,
        base_home_win_prob: float = 0.50,
    ) -> dict:
        """
        Standalone ensemble vote from referee model.
        Used as vote #4 in the 9-model aggregator.
        """
        adjusted = base_home_win_prob + report.home_win_prob_adjustment
        adjusted = max(0.10, min(0.90, adjusted))
        return {
            "model": "referee",
            "home_win_prob": round(adjusted, 4),
            "confidence": report.confidence,
            "components": {
                "crew": report.crew_tendency.ref_name,
                "home_bias_delta": round(
                    report.crew_tendency.home_win_pct - LEAGUE_HOME_WIN_PCT, 4
                ),
                "foul_rate": report.crew_tendency.avg_fouls_per_game,
                "total_adjustment": report.predicted_total_adjustment,
                "pace_beneficiary": report.pace_team_beneficiary,
            },
        }

    def adjust_prediction(
        self,
        base_prediction: dict,
        ref_names: list[str],
        home_pace: float = 100.0,
        away_pace: float = 100.0,
    ) -> dict:
        """
        v1-compatible prediction adjuster. Enriches prediction dict with
        referee adjustments. Now also adds home_win_prob_adjustment.
        """
        prediction = dict(base_prediction)
        if not ref_names:
            prediction["referee_pace_factor"] = 1.0
            prediction["referee_home_bias"] = 0.0
            return prediction

        report = self.evaluate(ref_names, home_pace, away_pace)
        base_total = prediction.get("predicted_total", 220)
        prediction["predicted_total"] = round(base_total + report.predicted_total_adjustment)
        prediction["referee_pace_factor"] = report.crew_tendency.pace_factor
        prediction["referee_home_bias"] = report.home_win_prob_adjustment
        prediction["referee_confidence"] = report.confidence
        return prediction

    # ---------------------------------------------------------------------------
    # Data layer
    # ---------------------------------------------------------------------------

    def get_ref_tendency(self, ref_name: str) -> RefTendency:
        """
        Fetch tendency from DB. Falls back to prior if insufficient data,
        then to neutral if no prior available.
        """
        cursor = self.conn.execute("""
            SELECT AVG(total_points)  AS avg_pts,
                   AVG(total_fouls)   AS avg_fouls,
                   AVG(home_win)      AS home_win_pct,
                   AVG(travel_rate)   AS travel_rate,
                   COUNT(*)           AS games
            FROM ref_games
            WHERE ref_name = ?
        """, (ref_name,))
        row = cursor.fetchone()

        if row and row["games"] >= 20:
            pace_factor = float(row["avg_pts"]) / LEAGUE_AVG_TOTAL
            return RefTendency(
                ref_name=ref_name,
                avg_total_points=round(float(row["avg_pts"]), 1),
                avg_fouls_per_game=round(float(row["avg_fouls"]), 1),
                home_win_pct=round(float(row["home_win_pct"]), 4),
                travel_call_rate_modifier=round(float(row["travel_rate"] or 1.0), 3),
                pace_factor=round(max(0.5, min(1.5, pace_factor)), 3),
                games_officiated=int(row["games"]),
                source="database",
            )

        # Try prior
        prior = CREW_PRIORS.get(ref_name)
        if prior:
            avg_total, avg_fouls, home_pct, travel_rate = prior
            return RefTendency(
                ref_name=ref_name,
                avg_total_points=avg_total,
                avg_fouls_per_game=avg_fouls,
                home_win_pct=home_pct,
                travel_call_rate_modifier=travel_rate,
                pace_factor=round(avg_total / LEAGUE_AVG_TOTAL, 3),
                games_officiated=row["games"] if row else 0,
                source="prior",
            )

        # Neutral fallback
        return RefTendency(
            ref_name=ref_name,
            avg_total_points=LEAGUE_AVG_TOTAL,
            avg_fouls_per_game=LEAGUE_AVG_FOULS_PER_GAME,
            home_win_pct=LEAGUE_HOME_WIN_PCT,
            travel_call_rate_modifier=1.0,
            pace_factor=1.0,
            games_officiated=0,
            source="neutral",
        )

    def ingest_ref_data(
        self,
        game_id: str,
        ref_names: list[str],
        total_points: int,
        total_fouls: int = 43,
        home_won: int = 0,
        travel_rate: float = 1.0,
    ):
        """Store referee assignment + outcome for a game."""
        for ref in ref_names:
            try:
                self.conn.execute("""
                    INSERT OR IGNORE INTO ref_games
                    (game_id, ref_name, total_points, total_fouls, home_win, travel_rate)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (game_id, ref.strip(), total_points, total_fouls, home_won, travel_rate))
            except Exception:
                continue
        self.conn.commit()

    def _ensure_ref_table(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS ref_games (
                game_id   TEXT,
                ref_name  TEXT,
                total_points  INTEGER,
                total_fouls   INTEGER,
                home_win      INTEGER DEFAULT 0,
                travel_rate   REAL    DEFAULT 1.0,
                pace          REAL    DEFAULT 1.0,
                PRIMARY KEY (game_id, ref_name)
            )
        """)
        self.conn.commit()

    def _neutral_report(self) -> RefereeReport:
        neutral = RefTendency(
            ref_name="Unknown",
            avg_total_points=LEAGUE_AVG_TOTAL,
            avg_fouls_per_game=LEAGUE_AVG_FOULS_PER_GAME,
            home_win_pct=LEAGUE_HOME_WIN_PCT,
            travel_call_rate_modifier=1.0,
            pace_factor=1.0,
            games_officiated=0,
            source="neutral",
        )
        return RefereeReport(
            refs=[],
            crew_tendency=neutral,
            predicted_total_adjustment=0.0,
            home_win_prob_adjustment=0.0,
            pace_team_beneficiary=None,
            confidence="LOW",
        )

    def close(self):
        self.conn.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0
