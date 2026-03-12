import pytest
import numpy as np
from src.ml.real_data_pipeline import (
    compute_rolling_win_pct,
    compute_rest_days,
    structure_game_logs,
    label_night_types,
)

def test_compute_rolling_win_pct():
    mock_games = [
        {"TEAM_ABBREVIATION": "BOS", "GAME_DATE": "2024-01-01", "WL": "W"},
        {"TEAM_ABBREVIATION": "BOS", "GAME_DATE": "2024-01-03", "WL": "L"},
        {"TEAM_ABBREVIATION": "BOS", "GAME_DATE": "2024-01-05", "WL": "W"},
        {"TEAM_ABBREVIATION": "NYK", "GAME_DATE": "2024-01-02", "WL": "W"},
    ]
    pct = compute_rolling_win_pct(mock_games, "BOS", "2024-01-06")
    assert pct == 0.6667

    pct_empty = compute_rolling_win_pct(mock_games, "BOS", "2023-12-01")
    assert pct_empty == 0.500

def test_compute_rest_days():
    mock_games = [
        {"TEAM_ABBREVIATION": "BOS", "GAME_DATE": "2024-01-01"},
        {"TEAM_ABBREVIATION": "BOS", "GAME_DATE": "2024-01-02"},
        {"TEAM_ABBREVIATION": "BOS", "GAME_DATE": "2024-01-05"},
    ]
    rest, is_b2b = compute_rest_days(mock_games, "BOS", "2024-01-03")
    assert rest == 1
    assert is_b2b is True

    rest, is_b2b = compute_rest_days(mock_games, "BOS", "2024-01-07")
    assert rest == 2
    assert is_b2b is False

def test_structure_game_logs():
    raw = [
        {"GAME_ID": "001", "TEAM_ABBREVIATION": "BOS", "MATCHUP": "BOS vs. NYK", "GAME_DATE": "2024-01-01", "PTS": 110, "E_OFF_RATING": 115.0},
        {"GAME_ID": "001", "TEAM_ABBREVIATION": "NYK", "MATCHUP": "NYK @ BOS", "GAME_DATE": "2024-01-01", "PTS": 105, "E_OFF_RATING": 110.0},
    ]
    structured = structure_game_logs(raw, "2023-24")
    assert len(structured) == 1
    g = structured[0]
    assert g["game_id"] == "001"
    assert g["home_team"] == "BOS"
    assert g["away_team"] == "NYK"
    assert g["home_win"] == 1
    assert g["home_ortg"] == 115.0

def test_label_night_types():
    logs = [
        {"player_id": "1", "points": 10},
        {"player_id": "1", "points": 10},
        {"player_id": "1", "points": 10},
        {"player_id": "1", "points": 100}, # Hot
        {"player_id": "1", "points": 15}, # Above avg
        {"player_id": "1", "points": -50},  # Cold
    ]
    labeled = label_night_types(logs)
    assert len(labeled) == 6
    types = [l["night_type"] for l in labeled]
    assert "hot" in types
    assert "cold" in types
