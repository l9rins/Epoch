from src.intelligence.kelly_criterion import (
    compute_full_kelly,
    compute_kelly_recommendation,
    american_to_decimal,
)
from decimal import Decimal

def test_american_to_decimal():
    assert round(float(american_to_decimal(-110)), 3) == 1.909
    assert float(american_to_decimal(150)) == 2.50
    assert float(american_to_decimal(-200)) == 1.50

def test_compute_full_kelly():
    # 60% win prob at +100 odds (b=1) = 0.60 - 0.40/1 = 0.20
    assert float(compute_full_kelly(Decimal("0.60"), Decimal("2.0"))) == 0.20
    # Negative edge = 0
    assert float(compute_full_kelly(Decimal("0.50"), Decimal("1.909"))) == 0.0

def test_tier_adjustments():
    # Tier 1 = Full * 0.5 * 1.0 (multiplier)
    t1 = compute_kelly_recommendation(
        "TEST", 1, 0.62, 10000.0, float(american_to_decimal(-110))
    )
    # Tier 2 = Full * 0.5 * 0.75
    t2 = compute_kelly_recommendation(
        "TEST", 2, 0.62, 10000.0, float(american_to_decimal(-110))
    )
    # Tier 3 = Full * 0.5 * 0.50
    t3 = compute_kelly_recommendation(
        "TEST", 3, 0.62, 10000.0, float(american_to_decimal(-110))
    )
    
    assert t1.recommended_fraction > t2.recommended_fraction
    assert t2.recommended_fraction > t3.recommended_fraction

def test_ruin_protection_and_caps():
    # Massive edge should still be capped at 25% * tier mult
    huge_edge = compute_kelly_recommendation("TEST", 1, 0.99, 10000.0, 2.0)
    assert float(huge_edge.recommended_fraction) <= 0.25
    
    # Tiny positive edge gets minimum 1% floor unless below absolute minimum EV threshold
    small_edge = compute_kelly_recommendation("TEST", 1, 0.53, 10000.0, 1.909)
    if small_edge.recommended_fraction > 0:
        assert float(small_edge.recommended_fraction) >= 0.01

def test_negative_edge_filtering():
    rec = compute_kelly_recommendation("TEST", 1, 0.40, 10000.0, 1.909)
    assert float(rec.recommended_bet_size) == 0.0
    assert rec.expected_value_per_dollar <= 0
    assert "below minimum threshold" in rec.reasoning
