"""
Tests for src/ml/real_data_pipeline.py
Covers: fallback chain, game log structuring, player log structuring,
        night type labeling, injury proxy extraction.
"""

import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.ml.real_data_pipeline import (
    DEFAULT_ALTITUDE_FT,
    DEFAULT_REST_DAYS,
    DEFAULT_WIN_PCT,
    NIGHT_TYPE_MIN_HISTORY,
    SEASONS_TO_PULL,
    TEAM_ALTITUDE_FT,
    _extract_injury_proxy_games,
    compute_rest_days,
    compute_rolling_win_pct,
    label_night_types,
    load_game_logs,
    load_injury_logs,
    load_player_logs,
    structure_game_logs,
    structure_player_logs,
)
from src.pipeline.bball_ref_fallback import (
    DATA_SOURCE_BALLDONTLIE,
    DATA_SOURCE_PRIMARY,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def raw_team_game_pair():
    """Two game records (home + away) for one game."""
    return [
        {
            "GAME_ID": "0022400001",
            "TEAM_ABBREVIATION": "BOS",
            "MATCHUP": "BOS vs. MIA",
            "GAME_DATE": "2024-10-22",
            "PTS": 115,
            "WL": "W",
            "E_OFF_RATING": 118.5,
            "E_DEF_RATING": 108.0,
            "PACE": 97.5,
            "L5_W": 3,
        },
        {
            "GAME_ID": "0022400001",
            "TEAM_ABBREVIATION": "MIA",
            "MATCHUP": "MIA @ BOS",
            "GAME_DATE": "2024-10-22",
            "PTS": 108,
            "WL": "L",
            "E_OFF_RATING": 109.0,
            "E_DEF_RATING": 116.0,
            "PACE": 97.5,
            "L5_W": 2,
        },
    ]


@pytest.fixture
def raw_player_log():
    return {
        "PLAYER_ID": "2544",
        "PLAYER_NAME": "LeBron James",
        "TEAM_ABBREVIATION": "LAL",
        "GAME_ID": "0022400050",
        "GAME_DATE": "2024-10-25",
        "MATCHUP": "LAL vs. MIN",
        "PTS": 28.0,
        "AST": 7.0,
        "REB": 8.0,
        "FG3M": 2.0,
        "STL": 1.0,
        "BLK": 0.0,
        "MIN": 36.0,
        "USG_PCT": 0.28,
        "TS_PCT": 0.598,
        "PLUS_MINUS": 5.0,
    }


@pytest.fixture
def multi_season_game_logs():
    """A small list of game logs for testing night types and injury proxy."""
    logs = []
    for i in range(20):
        logs.append({
            "game_id": f"game_{i}",
            "season": "2024-25",
            "game_date": f"2024-11-{(i % 28) + 1:02d}",
            "home_team": "BOS",
            "away_team": "MIA",
            "home_score": 110 + (i % 10),
            "away_score": 100 + (i % 8),
            "home_win": 1,
            "home_ortg": 112.0 if i != 5 else 90.0,  # game 5 is injury proxy
            "away_ortg": 108.0,
            "home_drtg": 108.0,
            "away_drtg": 112.0,
            "home_pace": 97.5,
            "away_pace": 97.5,
            "home_rest_days": 2,
            "away_rest_days": 2,
            "home_is_b2b": False,
            "away_is_b2b": False,
            "home_win_pct_prior": 0.60,
            "away_win_pct_prior": 0.40,
            "home_last_5_wins": 3,
            "away_last_5_wins": 2,
            "home_road_trip_game": 0,
            "away_road_trip_game": 0,
            "home_altitude_ft": 141,
            "away_altitude_ft": 6,
            "referee_crew_id": "",
            "predicted_home_wp": None,
            "actual_home_win": 1,
            "source": DATA_SOURCE_PRIMARY,
        })
    return logs


# ---------------------------------------------------------------------------
# compute_rolling_win_pct
# ---------------------------------------------------------------------------

class TestComputeRollingWinPct:
    def test_perfect_record(self):
        games = [
            {"TEAM_ABBREVIATION": "BOS", "GAME_DATE": "2024-10-20", "WL": "W"},
            {"TEAM_ABBREVIATION": "BOS", "GAME_DATE": "2024-10-22", "WL": "W"},
        ]
        result = compute_rolling_win_pct(games, "BOS", "2024-10-25")
        assert result == 1.0

    def test_no_prior_games_returns_default(self):
        result = compute_rolling_win_pct([], "BOS", "2024-10-22")
        assert result == DEFAULT_WIN_PCT

    def test_mixed_record(self):
        games = [
            {"TEAM_ABBREVIATION": "BOS", "GAME_DATE": "2024-10-20", "WL": "W"},
            {"TEAM_ABBREVIATION": "BOS", "GAME_DATE": "2024-10-21", "WL": "L"},
            {"TEAM_ABBREVIATION": "BOS", "GAME_DATE": "2024-10-22", "WL": "W"},
            {"TEAM_ABBREVIATION": "BOS", "GAME_DATE": "2024-10-23", "WL": "L"},
        ]
        result = compute_rolling_win_pct(games, "BOS", "2024-10-25")
        assert result == 0.5

    def test_ignores_future_games(self):
        games = [
            {"TEAM_ABBREVIATION": "BOS", "GAME_DATE": "2024-10-26", "WL": "W"},
        ]
        result = compute_rolling_win_pct(games, "BOS", "2024-10-25")
        assert result == DEFAULT_WIN_PCT


# ---------------------------------------------------------------------------
# compute_rest_days
# ---------------------------------------------------------------------------

class TestComputeRestDays:
    def test_back_to_back(self):
        games = [{"TEAM_ABBREVIATION": "LAL", "GAME_DATE": "2024-10-21"}]
        rest, b2b = compute_rest_days(games, "LAL", "2024-10-22")
        assert rest == 1
        assert b2b is True

    def test_two_days_rest(self):
        games = [{"TEAM_ABBREVIATION": "LAL", "GAME_DATE": "2024-10-20"}]
        rest, b2b = compute_rest_days(games, "LAL", "2024-10-22")
        assert rest == 2
        assert b2b is False

    def test_no_prior_games(self):
        rest, b2b = compute_rest_days([], "LAL", "2024-10-22")
        assert rest == DEFAULT_REST_DAYS
        assert b2b is False

    def test_uses_most_recent_game(self):
        games = [
            {"TEAM_ABBREVIATION": "LAL", "GAME_DATE": "2024-10-15"},
            {"TEAM_ABBREVIATION": "LAL", "GAME_DATE": "2024-10-20"},
        ]
        rest, b2b = compute_rest_days(games, "LAL", "2024-10-22")
        assert rest == 2


# ---------------------------------------------------------------------------
# structure_game_logs
# ---------------------------------------------------------------------------

class TestStructureGameLogs:
    def test_pairs_home_and_away(self, raw_team_game_pair):
        result = structure_game_logs(raw_team_game_pair, "2024-25")
        assert len(result) == 1
        game = result[0]
        assert game["home_team"] == "BOS"
        assert game["away_team"] == "MIA"

    def test_correct_score(self, raw_team_game_pair):
        result = structure_game_logs(raw_team_game_pair, "2024-25")
        game = result[0]
        assert game["home_score"] == 115
        assert game["away_score"] == 108

    def test_home_win_flag(self, raw_team_game_pair):
        result = structure_game_logs(raw_team_game_pair, "2024-25")
        assert result[0]["home_win"] == 1

    def test_altitude_lookup(self, raw_team_game_pair):
        result = structure_game_logs(raw_team_game_pair, "2024-25")
        assert result[0]["home_altitude_ft"] == TEAM_ALTITUDE_FT["BOS"]

    def test_unknown_team_altitude_default(self):
        pair = [
            {"GAME_ID": "X001", "TEAM_ABBREVIATION": "ZZZ", "MATCHUP": "ZZZ vs. YYY",
             "GAME_DATE": "2024-10-22", "PTS": 100, "WL": "W"},
            {"GAME_ID": "X001", "TEAM_ABBREVIATION": "YYY", "MATCHUP": "YYY @ ZZZ",
             "GAME_DATE": "2024-10-22", "PTS": 95, "WL": "L"},
        ]
        result = structure_game_logs(pair, "2024-25")
        assert result[0]["home_altitude_ft"] == DEFAULT_ALTITUDE_FT

    def test_balldontlie_source_passthrough(self):
        """balldontlie records should be returned as-is."""
        fake_records = [{"game_id": "bdl_1", "source": DATA_SOURCE_BALLDONTLIE}]
        result = structure_game_logs(fake_records, "2024-25", source=DATA_SOURCE_BALLDONTLIE)
        assert result == fake_records

    def test_skips_incomplete_game(self):
        """Games with only one team record should be skipped."""
        single_record = [
            {"GAME_ID": "X002", "TEAM_ABBREVIATION": "BOS", "MATCHUP": "BOS vs. MIA",
             "GAME_DATE": "2024-10-22", "PTS": 110, "WL": "W"},
        ]
        result = structure_game_logs(single_record, "2024-25")
        assert result == []


# ---------------------------------------------------------------------------
# structure_player_logs
# ---------------------------------------------------------------------------

class TestStructurePlayerLogs:
    def test_basic_structure(self, raw_player_log):
        result = structure_player_logs([raw_player_log], "2024-25")
        assert len(result) == 1
        log = result[0]
        assert log["player_name"] == "LeBron James"
        assert log["points"] == 28.0
        assert log["is_home"] is True

    def test_away_game_flag(self, raw_player_log):
        raw_player_log["MATCHUP"] = "LAL @ BOS"
        result = structure_player_logs([raw_player_log], "2024-25")
        assert result[0]["is_home"] is False

    def test_balldontlie_passthrough(self):
        fake = [{"player_name": "Test", "source": DATA_SOURCE_BALLDONTLIE}]
        result = structure_player_logs(fake, "2024-25", source=DATA_SOURCE_BALLDONTLIE)
        assert result == fake

    def test_handles_none_values(self, raw_player_log):
        raw_player_log["PTS"] = None
        raw_player_log["AST"] = None
        result = structure_player_logs([raw_player_log], "2024-25")
        assert result[0]["points"] == 0.0
        assert result[0]["assists"] == 0.0


# ---------------------------------------------------------------------------
# label_night_types
# ---------------------------------------------------------------------------

class TestLabelNightTypes:
    def _make_logs(self, player_id, pts_list):
        return [
            {
                "player_id": player_id,
                "player_name": "Player",
                "points": p,
                "night_type": None,
            }
            for p in pts_list
        ]

    def test_hot_night_labeled(self):
        logs = self._make_logs("P1", [20, 22, 21, 19, 20, 20, 21, 20, 19, 40])
        labeled = label_night_types(logs)
        assert labeled[-1]["night_type"] == "hot"

    def test_cold_night_labeled(self):
        logs = self._make_logs("P2", [20, 22, 21, 19, 20, 20, 21, 20, 19, 2])
        labeled = label_night_types(logs)
        assert labeled[-1]["night_type"] == "cold"

    def test_average_night_labeled(self):
        logs = self._make_logs("P3", [20, 21, 20, 19, 21, 20])
        labeled = label_night_types(logs)
        assert labeled[-1]["night_type"] == "average"

    def test_insufficient_history_defaults_average(self):
        logs = self._make_logs("P4", [20, 21])
        labeled = label_night_types(logs)
        assert labeled[-1]["night_type"] == "average"

    def test_all_logs_get_night_type(self):
        logs = self._make_logs("P5", [15, 18, 20, 22, 25, 12, 30, 8])
        labeled = label_night_types(logs)
        assert all(log["night_type"] is not None for log in labeled)


# ---------------------------------------------------------------------------
# _extract_injury_proxy_games
# ---------------------------------------------------------------------------

class TestExtractInjuryProxyGames:
    def test_flags_low_ortg_game(self, multi_season_game_logs):
        """Game 5 has ortg=90 vs avg ~112 — should be flagged."""
        proxies = _extract_injury_proxy_games(multi_season_game_logs)
        assert len(proxies) > 0

    def test_proxy_has_required_fields(self, multi_season_game_logs):
        proxies = _extract_injury_proxy_games(multi_season_game_logs)
        assert len(proxies) > 0
        proxy = proxies[0]
        required = [
            "game_id", "game_date", "injured_team", "injury_type",
            "player_ortg_impact", "win_probability_delta",
        ]
        for field in required:
            assert field in proxy

    def test_injury_type_is_proxy(self, multi_season_game_logs):
        proxies = _extract_injury_proxy_games(multi_season_game_logs)
        assert all(p["injury_type"] == "proxy" for p in proxies)

    def test_empty_logs_returns_empty(self):
        result = _extract_injury_proxy_games([])
        assert result == []


# ---------------------------------------------------------------------------
# load helpers
# ---------------------------------------------------------------------------

class TestLoadHelpers:
    def test_load_game_logs_missing_file(self, tmp_path, monkeypatch):
        import src.ml.real_data_pipeline as rdp
        monkeypatch.setattr(rdp, "GAME_LOGS_PATH", tmp_path / "missing.jsonl")
        assert load_game_logs() == []

    def test_load_player_logs_missing_file(self, tmp_path, monkeypatch):
        import src.ml.real_data_pipeline as rdp
        monkeypatch.setattr(rdp, "PLAYER_LOGS_PATH", tmp_path / "missing.jsonl")
        assert load_player_logs() == []

    def test_load_injury_logs_missing_file(self, tmp_path, monkeypatch):
        import src.ml.real_data_pipeline as rdp
        monkeypatch.setattr(rdp, "INJURY_LOGS_PATH", tmp_path / "missing.jsonl")
        assert load_injury_logs() == []

    def test_load_game_logs_reads_file(self, tmp_path, monkeypatch):
        import src.ml.real_data_pipeline as rdp
        path = tmp_path / "games.jsonl"
        path.write_text(json.dumps({"game_id": "001"}) + "\n")
        monkeypatch.setattr(rdp, "GAME_LOGS_PATH", path)
        result = load_game_logs()
        assert len(result) == 1
        assert result[0]["game_id"] == "001"
