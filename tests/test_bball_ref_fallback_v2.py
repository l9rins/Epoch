"""
Tests for src/pipeline/bball_ref_fallback.py — SESSION D Week 1
Covers: balldontlie tier 2.5, three-tier fallback chain,
        game structuring, standings parsing.

Network rule: NEVER hit real network in tests.
All HTTP calls mocked via unittest.mock.
"""

import pytest
from unittest.mock import MagicMock, patch

from src.pipeline.bball_ref_fallback import (
    DATA_SOURCE_BALLDONTLIE,
    DATA_SOURCE_FALLBACK,
    DATA_SOURCE_PRIMARY,
    _structure_bdl_game,
    _structure_bdl_player_stat,
    fetch_bball_ref_standings,
    fetch_balldontlie_games,
    nba_api_with_fallback,
    parse_bball_ref_standings,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def bdl_game_record():
    return {
        "id": 12345,
        "date": "2024-10-22T00:00:00.000Z",
        "home_team": {"abbreviation": "BOS", "id": 2},
        "visitor_team": {"abbreviation": "MIA", "id": 14},
        "home_team_score": 115,
        "visitor_team_score": 108,
    }


@pytest.fixture
def bdl_game_unplayed():
    return {
        "id": 99999,
        "date": "2025-04-01T00:00:00.000Z",
        "home_team": {"abbreviation": "LAL", "id": 13},
        "visitor_team": {"abbreviation": "GSW", "id": 9},
        "home_team_score": None,
        "visitor_team_score": None,
    }


@pytest.fixture
def bdl_player_stat():
    return {
        "player": {"id": 2544, "first_name": "LeBron", "last_name": "James"},
        "team": {"abbreviation": "LAL"},
        "game": {"id": 5000, "date": "2024-10-25T00:00:00.000Z"},
        "pts": 28,
        "ast": 7,
        "reb": 8,
        "fg3m": 2,
        "stl": 1,
        "blk": 0,
        "oreb": 2,
        "min": "36:00",
    }


@pytest.fixture
def minimal_standings_html():
    return """
    <html><body>
    <table id="confs_standings_E">
      <tbody>
        <tr class="full_table">
          <th data-stat="team_name">Boston Celtics*</th>
          <td data-stat="wins">60</td>
          <td data-stat="losses">22</td>
        </tr>
      </tbody>
    </table>
    <table id="confs_standings_W">
      <tbody>
        <tr class="full_table">
          <th data-stat="team_name">Oklahoma City Thunder</th>
          <td data-stat="wins">57</td>
          <td data-stat="losses">25</td>
        </tr>
      </tbody>
    </table>
    </body></html>
    """


# ---------------------------------------------------------------------------
# _structure_bdl_game
# ---------------------------------------------------------------------------

class TestStructureBdlGame:
    def test_returns_epoch_schema(self, bdl_game_record):
        result = _structure_bdl_game(bdl_game_record, "2024-25")
        assert result is not None
        assert result["home_team"] == "BOS"
        assert result["away_team"] == "MIA"
        assert result["home_score"] == 115
        assert result["away_score"] == 108
        assert result["home_win"] == 1

    def test_unplayed_game_returns_none(self, bdl_game_unplayed):
        result = _structure_bdl_game(bdl_game_unplayed, "2024-25")
        assert result is None

    def test_source_label(self, bdl_game_record):
        result = _structure_bdl_game(bdl_game_record, "2024-25")
        assert result["source"] == DATA_SOURCE_BALLDONTLIE

    def test_game_date_format(self, bdl_game_record):
        result = _structure_bdl_game(bdl_game_record, "2024-25")
        assert result["game_date"] == "2024-10-22"

    def test_away_win(self, bdl_game_record):
        bdl_game_record["home_team_score"] = 100
        bdl_game_record["visitor_team_score"] = 110
        result = _structure_bdl_game(bdl_game_record, "2024-25")
        assert result["home_win"] == 0

    def test_season_preserved(self, bdl_game_record):
        result = _structure_bdl_game(bdl_game_record, "2023-24")
        assert result["season"] == "2023-24"


# ---------------------------------------------------------------------------
# _structure_bdl_player_stat
# ---------------------------------------------------------------------------

class TestStructureBdlPlayerStat:
    def test_returns_epoch_schema(self, bdl_player_stat):
        result = _structure_bdl_player_stat(bdl_player_stat, "2024-25")
        assert result is not None
        assert result["player_name"] == "LeBron James"
        assert result["points"] == 28.0
        assert result["assists"] == 7.0

    def test_minutes_parsed_from_colon_format(self, bdl_player_stat):
        result = _structure_bdl_player_stat(bdl_player_stat, "2024-25")
        assert result["minutes"] == pytest.approx(36.0, abs=0.1)

    def test_minutes_parsed_from_int_format(self, bdl_player_stat):
        bdl_player_stat["min"] = "36"
        result = _structure_bdl_player_stat(bdl_player_stat, "2024-25")
        assert result["minutes"] == pytest.approx(36.0, abs=0.1)

    def test_source_label(self, bdl_player_stat):
        result = _structure_bdl_player_stat(bdl_player_stat, "2024-25")
        assert result["source"] == DATA_SOURCE_BALLDONTLIE

    def test_none_minutes_defaults_to_zero(self, bdl_player_stat):
        bdl_player_stat["min"] = None
        result = _structure_bdl_player_stat(bdl_player_stat, "2024-25")
        assert result["minutes"] == 0.0

    def test_team_abbreviation(self, bdl_player_stat):
        result = _structure_bdl_player_stat(bdl_player_stat, "2024-25")
        assert result["team"] == "LAL"


# ---------------------------------------------------------------------------
# fetch_balldontlie_games — mocked
# ---------------------------------------------------------------------------

class TestFetchBalldontlieGames:
    @patch("src.pipeline.bball_ref_fallback._fetch_json")
    def test_returns_structured_games(self, mock_fetch, bdl_game_record):
        mock_fetch.return_value = {
            "data": [bdl_game_record],
            "meta": {"next_cursor": None},
        }
        result = fetch_balldontlie_games(season="2024-25")
        assert len(result) == 1
        assert result[0]["home_team"] == "BOS"

    @patch("src.pipeline.bball_ref_fallback._fetch_json")
    def test_skips_unplayed_games(self, mock_fetch, bdl_game_unplayed):
        mock_fetch.return_value = {
            "data": [bdl_game_unplayed],
            "meta": {"next_cursor": None},
        }
        result = fetch_balldontlie_games(season="2024-25")
        assert result == []

    @patch("src.pipeline.bball_ref_fallback._fetch_json")
    def test_fetch_failure_returns_empty(self, mock_fetch):
        mock_fetch.return_value = None
        result = fetch_balldontlie_games(season="2024-25")
        assert result == []

    @patch("src.pipeline.bball_ref_fallback._fetch_json")
    def test_pagination_stops_on_no_cursor(self, mock_fetch, bdl_game_record):
        mock_fetch.side_effect = [
            {"data": [bdl_game_record], "meta": {"next_cursor": None}},
        ]
        result = fetch_balldontlie_games(season="2024-25")
        assert mock_fetch.call_count == 1
        assert len(result) == 1


# ---------------------------------------------------------------------------
# parse_bball_ref_standings
# ---------------------------------------------------------------------------

class TestParseBballRefStandings:
    def test_parses_east_and_west(self, minimal_standings_html):
        result = parse_bball_ref_standings(minimal_standings_html)
        assert "Boston Celtics" in result
        assert "Oklahoma City Thunder" in result

    def test_strips_playoff_asterisk(self, minimal_standings_html):
        result = parse_bball_ref_standings(minimal_standings_html)
        assert "Boston Celtics" in result
        assert "Boston Celtics*" not in result

    def test_win_loss_values(self, minimal_standings_html):
        result = parse_bball_ref_standings(minimal_standings_html)
        assert result["Boston Celtics"]["wins"] == 60
        assert result["Boston Celtics"]["losses"] == 22

    def test_source_label(self, minimal_standings_html):
        result = parse_bball_ref_standings(minimal_standings_html)
        assert result["Boston Celtics"]["source"] == DATA_SOURCE_FALLBACK

    def test_empty_html_returns_empty(self):
        assert parse_bball_ref_standings("") == {}

    def test_missing_table_returns_empty(self):
        html = "<html><body><p>nothing here</p></body></html>"
        assert parse_bball_ref_standings(html) == {}


# ---------------------------------------------------------------------------
# nba_api_with_fallback — three-tier chain
# ---------------------------------------------------------------------------

class TestNbaApiWithFallback:
    def test_tier1_success_returns_primary(self):
        primary_fn = MagicMock(return_value=[{"game_id": "001"}])
        result, source = nba_api_with_fallback(primary_fn, season="2024-25")
        assert source == DATA_SOURCE_PRIMARY
        assert len(result) == 1

    @patch("src.pipeline.bball_ref_fallback.fetch_balldontlie_games")
    def test_tier1_fail_falls_to_balldontlie(self, mock_bdl):
        mock_bdl.return_value = [{"game_id": "bdl_001", "source": DATA_SOURCE_BALLDONTLIE}]
        primary_fn = MagicMock(side_effect=Exception("nba_api down"))
        result, source = nba_api_with_fallback(primary_fn, season="2024-25")
        assert source == DATA_SOURCE_BALLDONTLIE
        assert len(result) == 1

    @patch("src.pipeline.bball_ref_fallback.fetch_balldontlie_games")
    @patch("src.pipeline.bball_ref_fallback.fetch_game_logs_fallback")
    def test_all_fail_falls_to_br(self, mock_br, mock_bdl):
        mock_bdl.return_value = []
        mock_br.return_value = [{"game_id": "br_001", "source": DATA_SOURCE_FALLBACK}]
        primary_fn = MagicMock(side_effect=Exception("nba_api down"))
        result, source = nba_api_with_fallback(primary_fn, season="2024-25")
        assert source == DATA_SOURCE_FALLBACK

    @patch("src.pipeline.bball_ref_fallback.fetch_balldontlie_games")
    @patch("src.pipeline.bball_ref_fallback.fetch_game_logs_fallback")
    def test_balldontlie_exception_falls_to_br(self, mock_br, mock_bdl):
        mock_bdl.side_effect = Exception("balldontlie down")
        mock_br.return_value = [{"game_id": "br_002"}]
        primary_fn = MagicMock(side_effect=Exception("nba_api down"))
        result, source = nba_api_with_fallback(primary_fn, season="2024-25")
        assert source == DATA_SOURCE_FALLBACK

    def test_primary_retried_max_times(self):
        call_count = 0
        def flaky_fn(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            raise Exception("fail")

        with patch("src.pipeline.bball_ref_fallback.fetch_balldontlie_games", return_value=[]):
            with patch("src.pipeline.bball_ref_fallback.fetch_game_logs_fallback", return_value=[]):
                with patch("src.pipeline.bball_ref_fallback.time.sleep"):
                    nba_api_with_fallback(flaky_fn, season="2024-25")

        from src.pipeline.bball_ref_fallback import MAX_RETRIES
        assert call_count == MAX_RETRIES
