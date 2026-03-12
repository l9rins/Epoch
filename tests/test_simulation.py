import os
import json
import time
import pytest
from unittest.mock import patch, MagicMock
from src.simulation.memory_reader import GameState, MemoryReader
from src.simulation.state_logger import StateLogger
from src.simulation.process_manager import get_nba2k14_pid
import pymem.exception

def test_process_manager_returns_pid():
    mock_proc = MagicMock()
    mock_proc.info = {'name': 'nba2k14.exe', 'pid': 1234}
    
    with patch('psutil.process_iter', return_value=[mock_proc]):
        pid = get_nba2k14_pid()
        assert pid == 1234

def test_process_manager_not_found():
    mock_proc = MagicMock()
    mock_proc.info = {'name': 'chrome.exe', 'pid': 5678}
    
    with patch('psutil.process_iter', return_value=[mock_proc]):
        pid = get_nba2k14_pid()
        assert pid is None

@patch('pymem.Pymem')
def test_memory_reader_returns_dummy_state(mock_pymem_class):
    mock_pm = MagicMock()
    # Emulate the raw memory read throwing an error so the fallback dummy state is returned
    mock_pm.read_int.side_effect = pymem.exception.MemoryReadError(0xDEADBEEF, 4)
    mock_pymem_class.return_value = mock_pm

    reader = MemoryReader(1234)
    state = reader.read_state()
    
    assert state is not None
    assert state.quarter == 1
    assert state.clock == 720.0
    assert state.home_score == 0
    assert state.away_score == 0

def test_state_logger_writes_jsonl(tmp_path):
    logger = StateLogger(log_dir=str(tmp_path))
    state1 = GameState(timestamp=100.0, quarter=1, clock=600.5, home_score=2, away_score=0, possession=0)
    state2 = GameState(timestamp=100.5, quarter=1, clock=600.0, home_score=2, away_score=3, possession=1)
    
    logger.log(state1)
    logger.log(state2)
    
    assert os.path.exists(logger.log_file)
    with open(logger.log_file, "r") as f:
        lines = f.readlines()
        
    assert len(lines) == 2
    data1 = json.loads(lines[0])
    data2 = json.loads(lines[1])
    
    assert data1["home_score"] == 2
    assert data2["away_score"] == 3
    assert data1["clock"] == 600.5


def test_log_enriched_writes_analytics(tmp_path):
    logger = StateLogger(log_dir=str(tmp_path))
    state = GameState(timestamp=100.0, quarter=2, clock=300.0, home_score=45, away_score=38, possession=1)
    
    logger.log_enriched(
        state,
        win_probability=0.6723,
        momentum=15.5,
        projected_home=102,
        projected_away=88,
        home_scoring_rate=2.5,
        away_scoring_rate=2.1,
        game_time_elapsed=1020.0,
    )
    
    with open(logger.log_file, "r") as f:
        data = json.loads(f.readline())
    
    # Raw state fields preserved
    assert data["quarter"] == 2
    assert data["home_score"] == 45
    assert data["away_score"] == 38
    
    # Analytics fields present and rounded
    assert data["win_probability"] == 0.6723
    assert data["momentum"] == 15.5
    assert data["projected_home"] == 102
    assert data["projected_away"] == 88
    assert data["home_scoring_rate"] == 2.5
    assert data["away_scoring_rate"] == 2.1
    assert data["game_time_elapsed"] == 1020.0
    assert data["score_differential"] == 7


def test_summary_returns_game_stats(tmp_path):
    logger = StateLogger(log_dir=str(tmp_path))
    
    # Simulate a short game
    state1 = GameState(timestamp=1000.0, quarter=1, clock=720.0, home_score=0, away_score=0, possession=0)
    state2 = GameState(timestamp=1030.0, quarter=4, clock=0.0, home_score=105, away_score=98, possession=1)
    
    logger.log_enriched(state1, win_probability=0.5, momentum=0.0)
    logger.log_enriched(state2, win_probability=0.95, momentum=40.0)
    
    summary = logger.summary()
    
    assert summary["ticks"] == 2
    assert summary["duration_seconds"] == 30.0
    assert summary["final_quarter"] == 4
    assert summary["final_home_score"] == 105
    assert summary["final_away_score"] == 98
    assert summary["winner"] == "HOME"
    assert summary["final_win_probability"] == 0.95
    assert summary["final_momentum"] == 40.0
    assert "log_file" in summary


def test_summary_empty_logger(tmp_path):
    logger = StateLogger(log_dir=str(tmp_path))
    summary = logger.summary()
    assert summary["ticks"] == 0
