import pytest
from src.intelligence.signal_validator import (
    compute_expected_calibration_error,
    validate_signal_tiers,
    get_dynamic_tier_thresholds,
)

def test_compute_ece():
    probs = [0.1, 0.2, 0.9, 0.95]
    acts = [0, 0, 1, 1]
    # Small test dataset: calibration on small bins will pass math Check NaN logic:
    ece = compute_expected_calibration_error(probs, acts, n_bins=2)
    assert ece < 0.2
    
    # Terrible calibration
    probs_bad = [0.9, 0.9, 0.1, 0.1]
    ece_bad = compute_expected_calibration_error(probs_bad, acts, n_bins=2)
    assert ece_bad > 0.5

def test_validate_signal_tiers_insufficient_data():
    report = validate_signal_tiers(journal_entries=[])
    assert report["total_resolved_signals"] == 0
    assert report["tier_metrics"][1]["status"] == "INSUFFICIENT_DATA"

def test_validate_signal_tiers_synthetic():
    entries = [
        {"tier": 1, "outcome": "WIN", "epoch_win_probability": 0.8},
        {"tier": 1, "outcome": "WIN", "epoch_win_probability": 0.75},
        {"tier": 1, "outcome": "WIN", "epoch_win_probability": 0.85},
        {"tier": 1, "outcome": "LOSS", "epoch_win_probability": 0.7},
    ] * 5 # 20 entries, 15W/5L, 75% precision
    
    report = validate_signal_tiers(journal_entries=entries)
    m = report["tier_metrics"][1]
    assert m["precision"] == 0.75
    assert m["target_met"] is True
    assert m["status"] == "TARGET_MET"

def test_dynamic_thresholds():
    report = {
        "tier_metrics": {
            1: {"precision": 0.50}, # Below target (0.65)
            2: {"precision": 0.70}, # Exceeds target (0.58)
        }
    }
    adjusted = get_dynamic_tier_thresholds(report)
    assert adjusted[1]["adjustment"] == "TIGHTENED"
    assert adjusted[1]["min_wp"] > 0.70 # Baseline
    
    assert adjusted[2]["adjustment"] == "RELAXED"
    assert adjusted[2]["min_wp"] < 0.62 # Baseline
