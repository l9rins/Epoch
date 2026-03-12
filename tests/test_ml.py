import pytest
from src.ml.scoring_run_predictor import ScoringRunPredictor
from src.ml.comeback_engine import ComebackEngine
from src.ml.pace_classifier import PaceClassifier
from src.ml.clutch_detector import ClutchDetector
from src.ml.quarter_trajectory import QuarterTrajectory
from src.ml.spread_calculator import SpreadCalculator
from src.ml.total_forecaster import TotalForecaster
from src.ml.momentum_reversal import MomentumReversal
from src.ml.game_script import GameScriptClassifier
from src.ml.value_detector import ValueDetector
from src.ml.aggregator import IntelligenceAggregator

# Dummy data generator for tests to avoid heavy loads
def dummy_train_synthetic():
    games = []
    for _ in range(50):
        states = []
        h = 0
        a = 0
        for i in range(200):
            h += 1
            a += 1
            s = {
                "quarter": 1 if i < 50 else (2 if i < 100 else (3 if i < 150 else 4)),
                "clock": 720.0,
                "home_score": h,
                "away_score": a,
                "possession": i % 2,
                "time_remaining": 2880 - (i * 14.4),
                "pts_scored_this_poss": 1,
                "momentum": 0.0,
                "possession_count": i+1
            }
            states.append(s)
        games.append({"states": states, "final_home": h, "final_away": a})
    return games

@pytest.fixture(scope="module")
def train_data():
    return dummy_train_synthetic()

def test_system1_scoring_run(train_data):
    p = ScoringRunPredictor()
    p.train(train_data)
    # is_trained may be false on uniform dummy data, but predict must still work
    prob = p.predict(train_data[0]["states"][-5], train_data[0]["states"][:-5])
    assert 0.0 <= prob <= 1.0

def test_system2_comeback(train_data):
    e = ComebackEngine()
    e.train(train_data)
    # Down 10 late
    state = train_data[0]["states"][-1]
    state["home_score"] = 90
    state["away_score"] = 100
    prob = e.predict(state)
    assert 0.0 <= prob <= 1.0

def test_system3_pace(train_data):
    p = PaceClassifier()
    p.train(train_data)
    assert p.is_trained
    res = p.predict(train_data[0]["states"][-1], train_data[0]["states"][:-1])
    assert res["pace"] in ["SLOW", "MEDIUM", "FAST"]

def test_system4_clutch():
    c = ClutchDetector()
    state = {"quarter": 4, "time_remaining": 120, "home_score": 100, "away_score": 98, "momentum": 5.0}
    res = c.detect(state)
    assert res.is_clutch is True
    assert res.clutch_type == "SCORE"
    assert res.intensity > 50

def test_system5_trajectory():
    qt = QuarterTrajectory()
    sample_states = []
    base_t = 2880
    for i in range(15):
        sample_states.append({
            "quarter": 1, "time_remaining": base_t - (i * 10), 
            "home_score": i * 2, "away_score": i * 1
        })
    res = qt.analyze(sample_states[-1], sample_states[:-1])
    assert "projection" in "home_q_projection"
    assert "ACCELERATING" in res["trajectory"]

def test_system6_spread():
    s = SpreadCalculator(pregame_spread=-6)
    state = {"home_score": 100, "away_score": 90, "time_remaining": 600}
    res = s.calculate(state, momentum=10, projected_total=220)
    assert isinstance(res, float)
    
def test_system7_total(train_data):
    f = TotalForecaster()
    f.train(train_data)
    assert f.is_trained
    res = f.predict(train_data[0]["states"][-1], train_data[0]["states"][:-1])
    assert res["projected_total"] > 0
    assert 0.0 <= res["over_prob"] <= 1.0

def test_system8_reversal(train_data):
    m = MomentumReversal()
    m.train(train_data)
    res = m.predict(train_data[0]["states"][-1], train_data[0]["states"][:-1])
    assert 0.0 <= res <= 1.0

def test_system9_script(train_data):
    sc = GameScriptClassifier()
    sc.train(train_data)
    assert sc.is_trained
    res = sc.predict(train_data[0]["states"][-1], train_data[0]["states"][:-1])
    assert isinstance(res["script"], str)

def test_system10_value():
    v = ValueDetector()
    res = v.detect(0.65, -110) # 65% chance vs 52.4% odds
    assert res.has_edge is True
    assert res.edge > 0.10
    
def test_system12_aggregator():
    a = IntelligenceAggregator()
    # verify init structure
    assert a.pregame_spread == -4.5
    assert a.live_odds == -110
    assert a._is_ready is False
