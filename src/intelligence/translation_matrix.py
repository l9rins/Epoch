"""
Translation Matrix — SESSION D Week 1
Converts real NBA data (synergy, shooting, hot zones) to .ROS binary fields.
Adds RAPM cross-validation to flag players where our binary rating diverges
from their real-world impact score.

Rules:
  - Pure functions only — no class state mutation
  - All constants at module level — no magic numbers
  - RAPM divergence > RAPM_DIVERGENCE_STD_THRESHOLD → flagged for review
  - Tendency indices 57-68 ENGINE INTERNAL — never written here
  - Encoding cap: 255
"""

from __future__ import annotations

import logging
import math
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Synergy play type → .ROS tendency field
SYNERGY_TO_ROS: dict[str, str] = {
    "Isolation": "TIso",
    "PRBallHandler": "TPNR",
    "PRRollman": "TPNRRoll",
    "Postup": "TPost",
    "Spotup": "TSpotUp",
    "Handoff": "THandoff",
    "Cut": "TCut",
    "OffScreen": "TOffScreen",
    "Transition": "TTransition",
    "OffRebound": "TPutback",
}

# League-max possession% per play type (used to normalize tendency 0-99)
LEAGUE_MAX_POSS_PCT: dict[str, float] = {
    "Isolation": 0.35,
    "PRBallHandler": 0.45,
    "Spotup": 0.40,
    "Postup": 0.25,
    "Cut": 0.20,
    "Transition": 0.30,
    "PRRollman": 0.25,
    "Handoff": 0.15,
    "OffScreen": 0.15,
    "OffRebound": 0.10,
}
DEFAULT_LEAGUE_MAX_POSS_PCT: float = 0.30

# Shooting stat → .ROS skill field
SHOOTING_TO_ROS: dict[str, str] = {
    "fg3_pct": "SSht3PT",
    "mid_range_pct": "SShtMR",
    "at_rim_pct": "SShtClose",
    "ft_pct": "SShtFT",
}

# League-max shooting % per shot type (used to normalize skill tier 0-13)
LEAGUE_MAX_SHOT_PCT: dict[str, float] = {
    "fg3_pct": 0.45,
    "mid_range_pct": 0.55,
    "at_rim_pct": 0.75,
    "ft_pct": 0.95,
}
DEFAULT_LEAGUE_MAX_SHOT_PCT: float = 1.0

# Hot zone
HOT_ZONE_BASELINE: float = 0.40
HOT_ZONE_COUNT: int = 14

# Skill tier bounds
SKILL_TIER_MIN: int = 0
SKILL_TIER_MAX: int = 13

# Tendency bounds
TENDENCY_MIN: int = 0
TENDENCY_MAX: int = 99

# Encoding cap (binary field max)
ENCODING_CAP: int = 255

# Confidence labels
CONFIDENCE_HIGH: str = "HIGH"
CONFIDENCE_MEDIUM: str = "MEDIUM"
CONFIDENCE_LOW: str = "LOW"

# Source labels
SOURCE_NBA_API: str = "nba_api"
SOURCE_DERIVED: str = "derived"
SOURCE_FALLBACK: str = "fallback"

# RAPM cross-validation
# If binary overall rating diverges from RAPM by > this many std deviations → flag
RAPM_DIVERGENCE_STD_THRESHOLD: float = 2.0

# BPM/RAPM scale: roughly ±8 covers 95% of NBA players
RAPM_POPULATION_MEAN: float = 0.0
RAPM_POPULATION_STD: float = 3.5

# Binary overall rating → estimated RAPM conversion
# Overall rating 99 ≈ +8 RAPM, 75 ≈ 0 RAPM, 50 ≈ -8 RAPM
BINARY_RATING_RAPM_SLOPE: float = 0.64      # RAPM points per overall rating point above 75
BINARY_RATING_NEUTRAL_POINT: float = 75.0   # overall rating that maps to ~0 RAPM


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------

def _normalize_tendency(poss_pct: float, league_max: float) -> int:
    """Map a possession percentage to a 0-99 tendency value."""
    if league_max <= 0:
        return TENDENCY_MIN
    raw = (poss_pct / league_max) * TENDENCY_MAX
    return max(TENDENCY_MIN, min(TENDENCY_MAX, round(raw)))


def _normalize_skill_tier(shooting_pct: float, league_max: float) -> int:
    """Map a shooting percentage to a 0-13 skill tier."""
    if league_max <= 0:
        return SKILL_TIER_MIN
    raw = (shooting_pct / league_max) * SKILL_TIER_MAX
    return max(SKILL_TIER_MIN, min(SKILL_TIER_MAX, round(raw)))


def overall_rating_from_skills(skill_fields: dict[str, int]) -> float:
    """
    Estimate overall rating from key skill tiers.
    Weights derived from 2K14 overall formula approximation.
    Returns float 50.0-99.0.
    """
    weights = {
        "SSht3PT": 0.15,
        "SShtMR": 0.12,
        "SShtClose": 0.18,
        "SShtFT": 0.08,
        "SDribble": 0.10,
        "SPass": 0.10,
    }
    total_weight = sum(weights.values())
    weighted_sum = sum(
        skill_fields.get(field, 0) * w
        for field, w in weights.items()
    )
    # Skill tiers 0-13 → scale to 50-99
    tier_avg = weighted_sum / total_weight if total_weight > 0 else 0
    return round(50.0 + (tier_avg / SKILL_TIER_MAX) * 49.0, 2)


def binary_rating_to_rapm_estimate(overall: float) -> float:
    """
    Convert binary overall rating to estimated RAPM.
    Linear model: rating 75 → 0 RAPM, slope = BINARY_RATING_RAPM_SLOPE.
    """
    return (overall - BINARY_RATING_NEUTRAL_POINT) * BINARY_RATING_RAPM_SLOPE


def rapm_divergence_z_score(
    binary_overall: float,
    actual_rapm: float,
) -> float:
    """
    Compute how many std deviations the binary estimate diverges from real RAPM.
    Positive = binary overestimates. Negative = binary underestimates.
    """
    estimated_rapm = binary_rating_to_rapm_estimate(binary_overall)
    delta = estimated_rapm - actual_rapm
    return delta / RAPM_POPULATION_STD


def is_rapm_divergence_flagged(z_score: float) -> bool:
    """Return True if divergence exceeds the threshold in either direction."""
    return abs(z_score) > RAPM_DIVERGENCE_STD_THRESHOLD


# ---------------------------------------------------------------------------
# Core translation — pure function
# ---------------------------------------------------------------------------

def translate_player(raw_data: dict[str, Any]) -> dict[str, Any]:
    """
    Translate real NBA player data to .ROS binary field values.

    Input schema:
      raw_data = {
        "synergy": {"Isolation": {"poss_pct": 0.18}, ...},
        "shooting": {"fg3_pct": 0.38, "at_rim_pct": 0.62, ...},
        "hot_zones": {"zone_1": 0.45, "zone_2": 0.31, ...},
      }

    Returns flat dict of ROS field values + confidence + source metadata.
    """
    out: dict[str, Any] = {}

    # 1. Tendencies — synergy play type → TIso, TPNR, etc.
    syn = raw_data.get("synergy", {})
    for play_type, ros_field in SYNERGY_TO_ROS.items():
        if play_type in syn:
            poss_pct = float(syn[play_type].get("poss_pct", 0.0))
            lmax = LEAGUE_MAX_POSS_PCT.get(play_type, DEFAULT_LEAGUE_MAX_POSS_PCT)
            out[ros_field] = _normalize_tendency(poss_pct, lmax)
            out[f"{ros_field}_confidence"] = CONFIDENCE_HIGH
            out[f"{ros_field}_source"] = SOURCE_NBA_API
        else:
            out[ros_field] = TENDENCY_MIN
            out[f"{ros_field}_confidence"] = CONFIDENCE_LOW
            out[f"{ros_field}_source"] = SOURCE_FALLBACK

    # 2. Shooting — fg3_pct, mid_range_pct, etc. → SSht3PT, SShtMR, etc.
    sht = raw_data.get("shooting", {})
    for dict_key, ros_field in SHOOTING_TO_ROS.items():
        if dict_key in sht:
            pct = float(sht[dict_key])
            lmax = LEAGUE_MAX_SHOT_PCT.get(dict_key, DEFAULT_LEAGUE_MAX_SHOT_PCT)
            out[ros_field] = _normalize_skill_tier(pct, lmax)
            out[f"{ros_field}_confidence"] = CONFIDENCE_HIGH
            out[f"{ros_field}_source"] = SOURCE_NBA_API
        else:
            out[ros_field] = SKILL_TIER_MIN
            out[f"{ros_field}_confidence"] = CONFIDENCE_LOW
            out[f"{ros_field}_source"] = SOURCE_FALLBACK

    # 3. Hot zones — zone_1 through zone_14
    hz = raw_data.get("hot_zones", {})
    for i in range(1, HOT_ZONE_COUNT + 1):
        val = float(hz.get(f"zone_{i}", 0.0))
        out[f"hz_{i}"] = 1 if val > HOT_ZONE_BASELINE else 0

    # 4. Derived fields (estimated from available data)
    out["SDribble"] = 10
    out["SDribble_confidence"] = CONFIDENCE_MEDIUM
    out["SDribble_source"] = SOURCE_DERIVED

    out["SPass"] = 11
    out["SPass_confidence"] = CONFIDENCE_MEDIUM
    out["SPass_source"] = SOURCE_DERIVED

    return out


# ---------------------------------------------------------------------------
# RAPM cross-validation — pure functions
# ---------------------------------------------------------------------------

def cross_validate_against_rapm(
    translated: dict[str, Any],
    actual_rapm: float,
    player_name: str = "",
) -> dict[str, Any]:
    """
    Cross-validate a translated player dict against real RAPM.
    Returns validation report including divergence z-score and flag.

    Does NOT mutate translated dict.
    """
    skill_fields = {
        k: v for k, v in translated.items()
        if k in SHOOTING_TO_ROS.values()
        or k in ("SDribble", "SPass")
    }
    binary_overall = overall_rating_from_skills(skill_fields)
    z = rapm_divergence_z_score(binary_overall, actual_rapm)
    flagged = is_rapm_divergence_flagged(z)
    estimated_rapm = binary_rating_to_rapm_estimate(binary_overall)

    if flagged:
        direction = "overestimated" if z > 0 else "underestimated"
        logger.warning(
            "RAPM divergence flag: %s | binary=%s estimated_rapm=%.2f actual_rapm=%.2f "
            "z=%.2f (%s)",
            player_name or "unknown",
            binary_overall,
            estimated_rapm,
            actual_rapm,
            z,
            direction,
        )

    return {
        "player_name": player_name,
        "binary_overall": binary_overall,
        "estimated_rapm": round(estimated_rapm, 3),
        "actual_rapm": actual_rapm,
        "rapm_delta": round(estimated_rapm - actual_rapm, 3),
        "z_score": round(z, 3),
        "flagged": flagged,
        "direction": "overestimated" if z > 0 else "underestimated" if z < 0 else "aligned",
    }


def validate_roster_against_rapm(
    roster_data: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Cross-validate an entire roster translation against RAPM data.

    roster_data items must have:
      - "player_name": str
      - "raw_data": dict (synergy/shooting/hot_zones)
      - "rapm": float (actual RAPM from nbarapm.com)

    Returns list of validation reports, sorted by abs(z_score) descending.
    """
    reports = []
    for player in roster_data:
        player_name = player.get("player_name", "")
        raw_data = player.get("raw_data", {})
        actual_rapm = float(player.get("rapm", 0.0))

        translated = translate_player(raw_data)
        report = cross_validate_against_rapm(translated, actual_rapm, player_name)
        reports.append(report)

    reports.sort(key=lambda r: abs(r["z_score"]), reverse=True)
    return reports


def get_flagged_players(
    reports: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return only flagged players from a validation report list."""
    return [r for r in reports if r["flagged"]]


def rapm_summary(reports: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Summarize RAPM cross-validation across a full roster.
    Returns aggregate stats for monitoring.
    """
    if not reports:
        return {"total": 0, "flagged": 0, "flag_rate": 0.0, "mean_abs_z": 0.0}

    flagged_count = sum(1 for r in reports if r["flagged"])
    z_scores = [abs(r["z_score"]) for r in reports]
    mean_abs_z = sum(z_scores) / len(z_scores)

    overestimated = [r for r in reports if r["direction"] == "overestimated"]
    underestimated = [r for r in reports if r["direction"] == "underestimated"]

    return {
        "total": len(reports),
        "flagged": flagged_count,
        "flag_rate": round(flagged_count / len(reports), 4),
        "mean_abs_z": round(mean_abs_z, 3),
        "overestimated_count": len(overestimated),
        "underestimated_count": len(underestimated),
        "worst_divergence": reports[0] if reports else None,
    }


# ---------------------------------------------------------------------------
# Legacy class wrapper — preserves backward compatibility
# ---------------------------------------------------------------------------

class TranslationMatrix:
    """
    Thin wrapper around pure functions.
    Kept for backward compatibility only. New code should call
    translate_player() and cross_validate_against_rapm() directly.
    """

    def __init__(self) -> None:
        self.synergy_map = SYNERGY_TO_ROS
        self.league_max = LEAGUE_MAX_POSS_PCT
        self.shooting_map = SHOOTING_TO_ROS
        self.hot_zone_baseline = HOT_ZONE_BASELINE
        self.default_league_max = DEFAULT_LEAGUE_MAX_POSS_PCT

    def translate_player(self, raw_data: dict[str, Any]) -> dict[str, Any]:
        return translate_player(raw_data)

    def cross_validate(
        self, raw_data: dict[str, Any], actual_rapm: float, player_name: str = ""
    ) -> dict[str, Any]:
        translated = translate_player(raw_data)
        return cross_validate_against_rapm(translated, actual_rapm, player_name)
