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
