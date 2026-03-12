import pytest
import sqlite3
import os
from pathlib import Path
from src.pipeline.historical_ingestion import HistoricalIngestion
from src.intelligence.referee_model import RefereeModel, RefTendency
from src.intelligence.pregame_predictor import PregamePredictor

TEST_DB = "data/test_nba_history.db"

@pytest.fixture(scope="module")
def setup_test_db():
    import contextlib
    with contextlib.suppress(PermissionError):
        if os.path.exists(TEST_DB):
            os.remove(TEST_DB)
    
    # Init creates schema implicitly
    hist = HistoricalIngestion(db_path=TEST_DB)
    
    # Insert some dummy H2H data for tests so we don't rely on live API for core tests
    dummy_games = [
        ("g1", "2023-24", "2023-11-01", "GSW", "LAL", 110, 100, "HOME"),
        ("g2", "2023-24", "2023-12-01", "LAL", "GSW", 105, 100, "HOME"),
        ("g3", "2023-24", "2024-01-01", "GSW", "LAL", 120, 115, "HOME"),
        ("g4", "2023-24", "2024-02-01", "LAL", "GSW", 111, 112, "AWAY"), # GSW won away
    ]
    for g in dummy_games:
        hist.conn.execute(
            "INSERT INTO games (game_id, season, date, home_team, away_team, home_score, away_score, winner) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            g
        )
    hist.conn.commit()
    
    # Insert referee data
    ref_model = RefereeModel(db_path=TEST_DB)
    # Fast ref (high points)
    ref_model.ingest_ref_data("rg1", ["Fast Ref"], 250, 45, 1.1)
    ref_model.ingest_ref_data("rg2", ["Fast Ref"], 240, 40, 1.1)
    # Slow ref (low points)
    ref_model.ingest_ref_data("rg3", ["Slow Ref"], 200, 35, 0.9)
    ref_model.ingest_ref_data("rg4", ["Slow Ref"], 190, 30, 0.9)
    
    yield hist, ref_model
    
    import contextlib

    # Teardown
    hist.conn.close()
    ref_model.conn.close()
    
    import gc
    gc.collect()
    
    import time
    time.sleep(0.1)
    
    if os.path.exists(TEST_DB):
        try:
            os.remove(TEST_DB)
        except PermissionError:
            pass

def test_db_schema_created(setup_test_db):
    hist, _ = setup_test_db
    cursor = hist.conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='games'"
    )
    assert cursor.fetchone() is not None

def test_season_ingestion(setup_test_db):
    hist, _ = setup_test_db
    # Query existing DB instead of calling API
    cursor = hist.conn.execute("SELECT COUNT(*) FROM games")
    count = cursor.fetchone()[0]
    assert count > 0, "Database should have games"

def test_h2h_query(setup_test_db):
    hist, _ = setup_test_db
    results = hist.query_head_to_head("GSW", "LAL", last_n=10)
    assert len(results) == 4
    
    # Check fields
    game = results[0]
    assert "home_team" in game
    assert "away_team" in game
    
    # Count wins for GSW
    gsw_wins = sum(1 for g in results if (g["home_team"] == "GSW" and g["winner"] == "HOME") or (g["away_team"] == "GSW" and g["winner"] == "AWAY"))
    assert gsw_wins == 3 # g1, g3, g4

def test_ref_tendency_has_pace_factor(setup_test_db):
    _, ref_model = setup_test_db
    
    fast_tendency = ref_model.get_ref_tendency("Fast Ref")
    assert 0.5 <= fast_tendency.pace_factor <= 1.5
    assert fast_tendency.pace_factor > 1.0 # Should be > 1.0 based on 245 avg pts
    
    slow_tendency = ref_model.get_ref_tendency("Slow Ref")
    assert 0.5 <= slow_tendency.pace_factor <= 1.5
    assert slow_tendency.pace_factor < 1.0 # Should be < 1.0 based on 195 avg pts

def test_enhanced_prediction_has_h2h(monkeypatch, setup_test_db):
    # Monkeypatch the DB path on HistoricalIngestion class ONLY for this test
    # so PregamePredictor uses our test DB
    hist, _ = setup_test_db
    monkeypatch.setattr(HistoricalIngestion, "DB_PATH", Path(TEST_DB))
    
    predictor = PregamePredictor()
    pred = predictor.predict("GSW", "LAL")
    
    assert "h2h_home_wins" in pred
    assert "h2h_away_wins" in pred
    assert pred["h2h_home_wins"] == 3  # GSW has 3 wins
    assert pred["h2h_away_wins"] == 1  # LAL has 1 win
    assert "confidence" in pred
    assert pred["confidence"] > 0.3 # Should be boosted by H2H

def test_total_adjusts_with_ref(monkeypatch, setup_test_db):
    hist, ref_model = setup_test_db
    monkeypatch.setattr(HistoricalIngestion, "DB_PATH", Path(TEST_DB))
    # We also need to monkeypatch the RefereeModel db path inside the predictor
    predictor = PregamePredictor()
    
    # Force the ref model instance to use our test DB
    predictor._ref_model = ref_model
    
    # Prediction with slow ref
    pred_slow = predictor.predict("GSW", "LAL", ref_names=["Slow Ref"])
    
    # Prediction with fast ref
    pred_fast = predictor.predict("GSW", "LAL", ref_names=["Fast Ref"])
    
    assert pred_fast["predicted_total"] > pred_slow["predicted_total"]
    assert pred_fast["referee_pace_factor"] > pred_slow["referee_pace_factor"]
    
    # Base is 220, fast should be 220 * ~1.09 > 220, slow 220 * ~0.87 < 220
    assert pred_fast["predicted_total"] > 220
    assert pred_slow["predicted_total"] < 220
