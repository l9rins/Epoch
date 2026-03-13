"""
Tests for src/intelligence/translation_matrix.py
Covers: translation, RAPM cross-validation, divergence flagging,
        roster-level validation, summary stats.
"""

import pytest

from src.intelligence.translation_matrix import (
    CONFIDENCE_HIGH,
    CONFIDENCE_LOW,
    CONFIDENCE_MEDIUM,
    ENCODING_CAP,
    HOT_ZONE_COUNT,
    RAPM_DIVERGENCE_STD_THRESHOLD,
    SKILL_TIER_MAX,
    SKILL_TIER_MIN,
    TENDENCY_MAX,
    TENDENCY_MIN,
    TranslationMatrix,
    _normalize_skill_tier,
    _normalize_tendency,
    binary_rating_to_rapm_estimate,
    cross_validate_against_rapm,
    get_flagged_players,
    is_rapm_divergence_flagged,
    overall_rating_from_skills,
    rapm_divergence_z_score,
    rapm_summary,
    translate_player,
    validate_roster_against_rapm,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def full_raw_data():
    """Full player data with synergy, shooting, hot zones."""
    return {
        "synergy": {
            "Isolation": {"poss_pct": 0.18},
            "PRBallHandler": {"poss_pct": 0.30},
            "Spotup": {"poss_pct": 0.20},
            "Transition": {"poss_pct": 0.15},
            "Cut": {"poss_pct": 0.10},
        },
        "shooting": {
            "fg3_pct": 0.38,
            "mid_range_pct": 0.45,
            "at_rim_pct": 0.62,
            "ft_pct": 0.82,
        },
        "hot_zones": {f"zone_{i}": 0.50 if i % 2 == 0 else 0.30 for i in range(1, 15)},
    }


@pytest.fixture
def empty_raw_data():
    return {"synergy": {}, "shooting": {}, "hot_zones": {}}


@pytest.fixture
def sample_roster():
    """Roster with RAPM values for cross-validation."""
    return [
        {
            "player_name": "Elite Player",
            "rapm": 6.5,
            "raw_data": {
                "synergy": {"PRBallHandler": {"poss_pct": 0.40}, "Isolation": {"poss_pct": 0.30}},
                "shooting": {"fg3_pct": 0.40, "at_rim_pct": 0.70, "ft_pct": 0.88, "mid_range_pct": 0.50},
                "hot_zones": {f"zone_{i}": 0.55 for i in range(1, 15)},
            },
        },
        {
            "player_name": "Average Player",
            "rapm": 0.2,
            "raw_data": {
                "synergy": {"Spotup": {"poss_pct": 0.20}},
                "shooting": {"fg3_pct": 0.35, "at_rim_pct": 0.55, "ft_pct": 0.75, "mid_range_pct": 0.40},
                "hot_zones": {f"zone_{i}": 0.38 for i in range(1, 15)},
            },
        },
        {
            "player_name": "Fringe Player",
            "rapm": -4.0,
            "raw_data": {
                "synergy": {},
                "shooting": {"fg3_pct": 0.28, "at_rim_pct": 0.42, "ft_pct": 0.60},
                "hot_zones": {},
            },
        },
    ]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class TestNormalizeHelpers:
    def test_tendency_at_league_max(self):
        assert _normalize_tendency(0.45, 0.45) == 99

    def test_tendency_at_zero(self):
        assert _normalize_tendency(0.0, 0.45) == 0

    def test_tendency_midpoint(self):
        result = _normalize_tendency(0.225, 0.45)
        assert result == 49 or result == 50  # rounding

    def test_tendency_capped_at_99(self):
        assert _normalize_tendency(1.0, 0.10) == 99

    def test_tendency_zero_league_max(self):
        assert _normalize_tendency(0.5, 0.0) == 0

    def test_skill_tier_at_max(self):
        assert _normalize_skill_tier(0.45, 0.45) == 13

    def test_skill_tier_at_zero(self):
        assert _normalize_skill_tier(0.0, 0.45) == 0

    def test_skill_tier_midpoint(self):
        result = _normalize_skill_tier(0.225, 0.45)
        assert SKILL_TIER_MIN <= result <= SKILL_TIER_MAX

    def test_skill_tier_zero_league_max(self):
        assert _normalize_skill_tier(0.5, 0.0) == 0


# ---------------------------------------------------------------------------
# translate_player
# ---------------------------------------------------------------------------

class TestTranslatePlayer:
    def test_returns_dict(self, full_raw_data):
        result = translate_player(full_raw_data)
        assert isinstance(result, dict)

    def test_tendency_fields_present(self, full_raw_data):
        result = translate_player(full_raw_data)
        assert "TIso" in result
        assert "TPNR" in result
        assert "TSpotUp" in result
        assert "TTransition" in result

    def test_shooting_fields_present(self, full_raw_data):
        result = translate_player(full_raw_data)
        assert "SSht3PT" in result
        assert "SShtMR" in result
        assert "SShtClose" in result
        assert "SShtFT" in result

    def test_hot_zone_flags_present(self, full_raw_data):
        result = translate_player(full_raw_data)
        for i in range(1, HOT_ZONE_COUNT + 1):
            assert f"hz_{i}" in result

    def test_hot_zone_above_baseline_is_1(self, full_raw_data):
        result = translate_player(full_raw_data)
        # Even zones have 0.50 > 0.40 baseline → should be 1
        assert result["hz_2"] == 1

    def test_hot_zone_below_baseline_is_0(self, full_raw_data):
        result = translate_player(full_raw_data)
        # Odd zones have 0.30 < 0.40 baseline → should be 0
        assert result["hz_1"] == 0

    def test_tendency_bounds(self, full_raw_data):
        result = translate_player(full_raw_data)
        assert TENDENCY_MIN <= result["TIso"] <= TENDENCY_MAX
        assert TENDENCY_MIN <= result["TPNR"] <= TENDENCY_MAX

    def test_skill_tier_bounds(self, full_raw_data):
        result = translate_player(full_raw_data)
        assert SKILL_TIER_MIN <= result["SSht3PT"] <= SKILL_TIER_MAX
        assert SKILL_TIER_MIN <= result["SShtClose"] <= SKILL_TIER_MAX

    def test_confidence_high_when_data_present(self, full_raw_data):
        result = translate_player(full_raw_data)
        assert result["TIso_confidence"] == CONFIDENCE_HIGH
        assert result["SSht3PT_confidence"] == CONFIDENCE_HIGH

    def test_confidence_low_when_missing(self, empty_raw_data):
        result = translate_player(empty_raw_data)
        assert result["TIso_confidence"] == CONFIDENCE_LOW
        assert result["SSht3PT_confidence"] == CONFIDENCE_LOW

    def test_derived_fields_present(self, full_raw_data):
        result = translate_player(full_raw_data)
        assert "SDribble" in result
        assert "SPass" in result
        assert result["SDribble_confidence"] == CONFIDENCE_MEDIUM
        assert result["SPass_confidence"] == CONFIDENCE_MEDIUM

    def test_missing_play_type_defaults_to_zero(self, empty_raw_data):
        result = translate_player(empty_raw_data)
        assert result["TIso"] == 0
        assert result["TPNR"] == 0

    def test_high_usage_iso_maps_near_99(self):
        data = {
            "synergy": {"Isolation": {"poss_pct": 0.34}},
            "shooting": {},
            "hot_zones": {},
        }
        result = translate_player(data)
        assert result["TIso"] >= 90

    def test_low_usage_iso_maps_near_0(self):
        data = {
            "synergy": {"Isolation": {"poss_pct": 0.01}},
            "shooting": {},
            "hot_zones": {},
        }
        result = translate_player(data)
        assert result["TIso"] < 10

    def test_does_not_mutate_input(self, full_raw_data):
        import copy
        original = copy.deepcopy(full_raw_data)
        translate_player(full_raw_data)
        assert full_raw_data == original

    def test_no_magic_numbers_in_output(self, full_raw_data):
        """All output values should be bounded by constants."""
        result = translate_player(full_raw_data)
        for key, val in result.items():
            if isinstance(val, int) and key.startswith("hz_"):
                assert val in (0, 1)
            elif isinstance(val, int) and key.startswith("T"):
                assert TENDENCY_MIN <= val <= TENDENCY_MAX
            elif isinstance(val, int) and key.startswith("S") and not key.endswith(("_confidence", "_source")):
                assert SKILL_TIER_MIN <= val <= ENCODING_CAP


# ---------------------------------------------------------------------------
# RAPM cross-validation
# ---------------------------------------------------------------------------

class TestRapmCrossValidation:
    def test_overall_rating_returns_float(self):
        skills = {"SSht3PT": 10, "SShtMR": 8, "SShtClose": 11, "SShtFT": 9, "SDribble": 10, "SPass": 11}
        result = overall_rating_from_skills(skills)
        assert isinstance(result, float)
        assert 50.0 <= result <= 99.0

    def test_overall_rating_empty_skills(self):
        result = overall_rating_from_skills({})
        assert result == 50.0

    def test_binary_to_rapm_at_neutral(self):
        """Rating 75 should map close to 0 RAPM."""
        result = binary_rating_to_rapm_estimate(75.0)
        assert abs(result) < 0.1

    def test_binary_to_rapm_elite_player(self):
        """High rating should produce positive RAPM."""
        result = binary_rating_to_rapm_estimate(99.0)
        assert result > 5.0

    def test_binary_to_rapm_bad_player(self):
        """Low rating should produce negative RAPM."""
        result = binary_rating_to_rapm_estimate(55.0)
        assert result < 0.0

    def test_rapm_z_score_aligned_player(self):
        """Player where binary matches RAPM → z near 0."""
        z = rapm_divergence_z_score(75.0, 0.0)
        assert abs(z) < 1.0

    def test_rapm_z_score_overestimated(self):
        """Binary says 99 but RAPM is 0 → overestimated."""
        z = rapm_divergence_z_score(99.0, 0.0)
        assert z > 0

    def test_rapm_z_score_underestimated(self):
        """Binary says 55 but RAPM is +5 → underestimated."""
        z = rapm_divergence_z_score(55.0, 5.0)
        assert z < 0

    def test_is_flagged_large_divergence(self):
        z = RAPM_DIVERGENCE_STD_THRESHOLD + 0.5
        assert is_rapm_divergence_flagged(z) is True

    def test_not_flagged_small_divergence(self):
        z = RAPM_DIVERGENCE_STD_THRESHOLD - 0.5
        assert is_rapm_divergence_flagged(z) is False

    def test_not_flagged_negative_small(self):
        z = -(RAPM_DIVERGENCE_STD_THRESHOLD - 0.5)
        assert is_rapm_divergence_flagged(z) is False

    def test_cross_validate_returns_report(self, full_raw_data):
        translated = translate_player(full_raw_data)
        report = cross_validate_against_rapm(translated, 2.5, "Test Player")
        assert "player_name" in report
        assert "binary_overall" in report
        assert "estimated_rapm" in report
        assert "actual_rapm" in report
        assert "rapm_delta" in report
        assert "z_score" in report
        assert "flagged" in report
        assert "direction" in report

    def test_cross_validate_direction_overestimated(self):
        """Give a low shooting player a very high RAPM claim — binary should underestimate."""
        raw = {
            "synergy": {},
            "shooting": {"fg3_pct": 0.20, "at_rim_pct": 0.35},
            "hot_zones": {},
        }
        translated = translate_player(raw)
        report = cross_validate_against_rapm(translated, 8.0, "Underestimated Star")
        assert report["direction"] == "underestimated"

    def test_cross_validate_does_not_mutate_translated(self, full_raw_data):
        import copy
        translated = translate_player(full_raw_data)
        original = copy.deepcopy(translated)
        cross_validate_against_rapm(translated, 2.5)
        assert translated == original


# ---------------------------------------------------------------------------
# Roster validation
# ---------------------------------------------------------------------------

class TestRosterValidation:
    def test_validate_roster_returns_list(self, sample_roster):
        reports = validate_roster_against_rapm(sample_roster)
        assert isinstance(reports, list)
        assert len(reports) == 3

    def test_sorted_by_abs_z_score(self, sample_roster):
        reports = validate_roster_against_rapm(sample_roster)
        z_scores = [abs(r["z_score"]) for r in reports]
        assert z_scores == sorted(z_scores, reverse=True)

    def test_get_flagged_players_filters(self, sample_roster):
        reports = validate_roster_against_rapm(sample_roster)
        flagged = get_flagged_players(reports)
        assert all(r["flagged"] for r in flagged)

    def test_rapm_summary_structure(self, sample_roster):
        reports = validate_roster_against_rapm(sample_roster)
        summary = rapm_summary(reports)
        assert "total" in summary
        assert "flagged" in summary
        assert "flag_rate" in summary
        assert "mean_abs_z" in summary
        assert "worst_divergence" in summary
        assert summary["total"] == 3

    def test_rapm_summary_empty(self):
        summary = rapm_summary([])
        assert summary["total"] == 0
        assert summary["flagged"] == 0
        assert summary["flag_rate"] == 0.0

    def test_rapm_summary_flag_rate_range(self, sample_roster):
        reports = validate_roster_against_rapm(sample_roster)
        summary = rapm_summary(reports)
        assert 0.0 <= summary["flag_rate"] <= 1.0


# ---------------------------------------------------------------------------
# Legacy class compatibility
# ---------------------------------------------------------------------------

class TestTranslationMatrixClass:
    def test_class_translate_player(self, full_raw_data):
        tm = TranslationMatrix()
        result = tm.translate_player(full_raw_data)
        assert "TIso" in result
        assert "SSht3PT" in result

    def test_class_cross_validate(self, full_raw_data):
        tm = TranslationMatrix()
        report = tm.cross_validate(full_raw_data, 2.5, "Test Player")
        assert "flagged" in report
        assert "z_score" in report

    def test_class_synergy_map_matches_constants(self):
        from src.intelligence.translation_matrix import SYNERGY_TO_ROS
        tm = TranslationMatrix()
        assert tm.synergy_map == SYNERGY_TO_ROS

    def test_class_league_max_matches_constants(self):
        from src.intelligence.translation_matrix import LEAGUE_MAX_POSS_PCT
        tm = TranslationMatrix()
        assert tm.league_max == LEAGUE_MAX_POSS_PCT
