"""
fatigue_model.py — Epoch Engine v2
Full fatigue model: schedule density, travel distance, altitude, minute-load,
age-curve, and back-to-back detection. Outputs a per-team fatigue scalar
(1.0 = fully rested, 0.0 = theoretically exhausted) AND an independent
win-probability vote that can sit alongside the RF/XGB/Elo votes in the
ensemble aggregator.

Upgrade from v1:
  - v1: 2 features (quarter + back-to-back binary)
  - v2: 9 features + age modifier + travel distance + altitude delta
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional


# ---------------------------------------------------------------------------
# Constants — never magic numbers
# ---------------------------------------------------------------------------

# NBA altitude map (feet above sea level) for arenas that matter
ARENA_ALTITUDE_FT: dict[str, float] = {
    "DEN": 5280.0,   # Ball Arena, Denver
    "UTA": 4327.0,   # Delta Center, Salt Lake City
    "OKC": 1201.0,   # Paycom Center, Oklahoma City
    "PHX": 1086.0,   # Footprint Center, Phoenix
    "DAL": 430.0,
    "SAS": 650.0,
    # Sea-level arenas default to 0
}

# Approximate straight-line distances (miles) used when travel data unavailable.
# Real pipeline can swap in actual flight distances from a lookup table.
CITY_COORDS_DEG: dict[str, tuple[float, float]] = {
    "BOS": (42.36, -71.06), "NYK": (40.75, -73.99), "BRK": (40.68, -73.97),
    "PHI": (39.90, -75.17), "TOR": (43.64, -79.38), "CHI": (41.88, -87.63),
    "CLE": (41.50, -81.69), "DET": (42.34, -83.05), "IND": (39.76, -86.16),
    "MIL": (43.04, -87.92), "ATL": (33.76, -84.40), "CHA": (35.23, -80.84),
    "MIA": (25.78, -80.19), "ORL": (28.54, -81.38), "WAS": (38.90, -77.02),
    "DEN": (39.74, -104.98), "MIN": (44.98, -93.27), "OKC": (35.46, -97.52),
    "POR": (45.52, -122.68), "UTA": (40.77, -111.90), "GSW": (37.77, -122.39),
    "LAC": (34.04, -118.27), "LAL": (34.04, -118.27), "PHX": (33.45, -112.07),
    "PHX_V2": (33.45, -112.07), # Dupe for safety
    "SAC": (38.58, -121.50), "HOU": (29.75, -95.36), "MEM": (35.14, -90.05),
    "NOP": (29.95, -90.08), "SAS": (29.43, -98.49), "DAL": (32.79, -96.81),
}

# Performance degradation per game within a 3-game window
B2B_PENALTY        = 0.060   # straight back-to-back
B2B_NIGHT_2_BONUS  = 0.020   # night-2 of B2B is slightly worse than night-1
THREE_IN_FOUR_PENALTY = 0.035
TRAVEL_PENALTY_PER_500MI = 0.008   # per 500 miles, max 0.04

# Altitude acclimatisation: non-Denver teams visiting high arenas
ALTITUDE_PENALTY_PER_1000FT = 0.006   # first visit penalty; halved if 2nd+ game week
SEA_LEVEL_ALTITUDE = 0.0

# Minute-load fatigue — rolling 3-game team minutes
# NBA team averages ~240 min/game. Heavy minutes = fatigue.
MINUTE_LOAD_BASELINE = 240.0          # per game (5 players × 48 min)
MINUTE_LOAD_PENALTY_PER_10 = 0.012    # per 10 mins above baseline, rolling 3g

# Age curve — star player age modifier on fatigue recovery
# After 32 fatigue compounds slightly; before 24 stamina is higher
def _age_recovery_modifier(age: float) -> float:
    """Returns a multiplier on fatigue penalty. Older = less recovery."""
    if age <= 24:
        return 0.85
    if age <= 28:
        return 1.00
    if age <= 31:
        return 1.10
    if age <= 34:
        return 1.22
    return 1.35   # 35+ (LeBron territory)

# Quarter late-game depletion (unchanged from v1 baseline, kept for continuity)
QUARTER_FATIGUE = {1: 1.00, 2: 0.97, 3: 0.94, 4: 0.90}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class TeamScheduleSnapshot:
    """All schedule context needed for one team on one game day."""
    team_id: str
    game_date: date
    opponent_arena_city: str            # e.g. "DEN"
    home_arena_city: str                # where team plays home games
    days_rest: int                      # 0 = B2B, 1 = 1 day rest, etc.
    games_last_7_days: int              # including tonight
    team_minutes_last_3_games: list[float]   # [g-3, g-2, g-1] minutes
    avg_player_age: float = 27.0
    is_home: bool = True
    prev_opponent_city: Optional[str] = None   # city they traveled FROM


@dataclass
class FatigueReport:
    """Full fatigue output for one team."""
    team_id: str
    fatigue_scalar: float          # 1.0 = fresh, lower = more tired
    win_prob_penalty: float        # raw adjustment to apply to base win prob
    components: dict[str, float]   # breakdown for scouting report
    confidence: str                # HIGH / MEDIUM / LOW


# ---------------------------------------------------------------------------
# Core model
# ---------------------------------------------------------------------------

class FatigueModel:
    """
    Epoch Engine v2 Fatigue Model.

    Usage:
        model = FatigueModel()
        home_report = model.evaluate(home_snapshot)
        away_report = model.evaluate(away_snapshot)
        adj_win_prob = model.adjust_win_probability(
            base_win_prob, home_report, away_report
        )
        vote = model.ensemble_vote(home_report, away_report)
    """

    # ---------------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------------

    def evaluate(self, snap: TeamScheduleSnapshot) -> FatigueReport:
        """
        Compute full fatigue report for a team given schedule context.
        Returns FatigueReport with scalar, penalty, and component breakdown.
        """
        components: dict[str, float] = {}

        # 1. Back-to-back / schedule density
        b2b_pen = self._schedule_penalty(snap)
        components["schedule_density"] = round(b2b_pen, 4)

        # 2. Travel distance penalty
        travel_pen = self._travel_penalty(snap)
        components["travel"] = round(travel_pen, 4)

        # 3. Altitude adjustment (only when visiting high-altitude arena)
        alt_pen = self._altitude_penalty(snap)
        components["altitude"] = round(alt_pen, 4)

        # 4. Minute-load fatigue
        load_pen = self._minute_load_penalty(snap)
        components["minute_load"] = round(load_pen, 4)

        # 5. Age modifier (amplifies all penalties)
        age_mod = _age_recovery_modifier(snap.avg_player_age)
        components["age_modifier"] = round(age_mod, 3)

        # Total penalty (before age modifier)
        raw_penalty = b2b_pen + travel_pen + alt_pen + load_pen
        # Age modifier compounds the non-structural penalties
        age_adjusted = (b2b_pen + load_pen) * age_mod + travel_pen + alt_pen
        total_penalty = min(age_adjusted, 0.30)   # hard cap

        fatigue_scalar = max(0.70, 1.0 - total_penalty)
        components["total_penalty"] = round(total_penalty, 4)

        # Confidence: low if we're missing data (e.g. no prior game cities)
        confidence = (
            "HIGH" if snap.prev_opponent_city and len(snap.team_minutes_last_3_games) == 3
            else "MEDIUM" if len(snap.team_minutes_last_3_games) >= 1
            else "LOW"
        )

        return FatigueReport(
            team_id=snap.team_id,
            fatigue_scalar=round(fatigue_scalar, 4),
            win_prob_penalty=round(total_penalty, 4),
            components=components,
            confidence=confidence,
        )

    def adjust_win_probability(
        self,
        base_win_prob: float,
        home_report: FatigueReport,
        away_report: FatigueReport,
    ) -> float:
        """
        Adjust base win probability using relative fatigue.
        Positive difference favors home team, negative favors away.
        """
        # Net differential: home fresh vs away tired = positive adjustment
        net = away_report.win_prob_penalty - home_report.win_prob_penalty
        # Scale: 10% swing per 0.10 differential (same calibration as v1)
        adjustment = net * 1.0
        adjusted = base_win_prob + adjustment
        return round(max(0.05, min(0.95, adjusted)), 4)

    def ensemble_vote(
        self,
        home_report: FatigueReport,
        away_report: FatigueReport,
        neutral_prob: float = 0.50,
    ) -> dict:
        """
        Return a standalone ensemble vote from fatigue alone.
        Used as vote #3 in the 9-model ensemble aggregator.

        Returns dict compatible with aggregator.py vote format:
            {"model": "fatigue", "home_win_prob": float, "confidence": str}
        """
        # Larger penalty difference = bigger swing from 50/50
        home_pen = home_report.win_prob_penalty
        away_pen = away_report.win_prob_penalty
        swing = (away_pen - home_pen) * 1.0   # same scale as adjust_win_probability

        home_win_prob = round(max(0.10, min(0.90, neutral_prob + swing)), 4)

        # Confidence degrades if either report is low-confidence
        if home_report.confidence == "HIGH" and away_report.confidence == "HIGH":
            conf = "HIGH"
        elif home_report.confidence == "LOW" or away_report.confidence == "LOW":
            conf = "LOW"
        else:
            conf = "MEDIUM"

        return {
            "model": "fatigue",
            "home_win_prob": home_win_prob,
            "confidence": conf,
            "components": {
                "home_penalty": home_report.win_prob_penalty,
                "away_penalty": away_report.win_prob_penalty,
                "net_swing": round(swing, 4),
                "home_fatigue_scalar": home_report.fatigue_scalar,
                "away_fatigue_scalar": away_report.fatigue_scalar,
            },
        }

    # ---------------------------------------------------------------------------
    # Feature extractors (private)
    # ---------------------------------------------------------------------------

    def _schedule_penalty(self, snap: TeamScheduleSnapshot) -> float:
        """B2B and 3-in-4 penalties."""
        penalty = 0.0
        if snap.days_rest == 0:
            penalty += B2B_PENALTY
            # Night 2 of a B2B is measurably worse — add small increment
            penalty += B2B_NIGHT_2_BONUS
        if snap.games_last_7_days >= 3:
            penalty += THREE_IN_FOUR_PENALTY
        return penalty

    def _travel_penalty(self, snap: TeamScheduleSnapshot) -> float:
        """
        Travel distance penalty based on previous city → current arena city.
        If home game, no travel penalty. If away, compute distance from prev city.
        """
        if snap.is_home:
            return 0.0
        if snap.prev_opponent_city is None:
            # No prior travel data — use a small default for away games
            return 0.010
        dist = _haversine_miles(snap.prev_opponent_city, snap.opponent_arena_city)
        penalty = (dist / 500.0) * TRAVEL_PENALTY_PER_500MI
        return min(penalty, 0.04)   # cap at 0.04 (2,500+ mile trips)

    def _altitude_penalty(self, snap: TeamScheduleSnapshot) -> float:
        """
        Altitude acclimatisation penalty for non-local teams.
        Only applies when visiting a high-altitude arena (DEN, UTA).
        """
        dest_alt = ARENA_ALTITUDE_FT.get(snap.opponent_arena_city, SEA_LEVEL_ALTITUDE)
        home_alt = ARENA_ALTITUDE_FT.get(snap.home_arena_city, SEA_LEVEL_ALTITUDE)

        # Only penalise if the destination is meaningfully higher than home
        alt_delta_ft = dest_alt - home_alt
        if alt_delta_ft <= 500:
            return 0.0

        penalty = (alt_delta_ft / 1000.0) * ALTITUDE_PENALTY_PER_1000FT
        return min(penalty, 0.025)

    def _minute_load_penalty(self, snap: TeamScheduleSnapshot) -> float:
        """
        Heavy-minutes penalty based on rolling 3-game team minute totals.
        Baseline: 240 min/game. Each 10 minutes above baseline = 0.012 penalty.
        """
        if not snap.team_minutes_last_3_games:
            return 0.0
        avg_mins = sum(snap.team_minutes_last_3_games) / len(snap.team_minutes_last_3_games)
        excess = max(0.0, avg_mins - MINUTE_LOAD_BASELINE)
        return min((excess / 10.0) * MINUTE_LOAD_PENALTY_PER_10, 0.03)

    # ---------------------------------------------------------------------------
    # Legacy v1 API (backwards compatibility)
    # ---------------------------------------------------------------------------

    def get_fatigue_factor(self, quarter: int, is_back_to_back: bool) -> float:
        """v1 compatibility shim."""
        base = QUARTER_FATIGUE.get(quarter, 0.90)
        if is_back_to_back:
            base -= 0.05
        return round(base, 2)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _haversine_miles(city_a: str, city_b: str) -> float:
    """Great-circle distance in miles between two NBA city codes."""
    if city_a == city_b:
        return 0.0
    coords_a = CITY_COORDS_DEG.get(city_a)
    coords_b = CITY_COORDS_DEG.get(city_b)
    if not coords_a or not coords_b:
        return 1000.0   # fallback: assume long trip

    lat1, lon1 = math.radians(coords_a[0]), math.radians(coords_a[1])
    lat2, lon2 = math.radians(coords_b[0]), math.radians(coords_b[1])

    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))
    return c * 3958.8   # Earth radius in miles
