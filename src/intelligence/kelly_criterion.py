from decimal import Decimal, ROUND_HALF_UP
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum
import json
from pathlib import Path
from datetime import datetime

# Constants — never use magic numbers
MAX_KELLY_FRACTION = Decimal("0.25")
HALF_KELLY_DIVISOR = Decimal("2")
MIN_SAMPLES_FOR_HISTORICAL = 30
PRIOR_HIT_RATE = Decimal("0.54")
PRIOR_WEIGHT = Decimal("0.30")
HISTORICAL_WEIGHT = Decimal("0.70")
MIN_EDGE_TO_BET = Decimal("0.02")   # 2% minimum edge threshold
DEFAULT_DECIMAL_ODDS = Decimal("1.91")  # -110 American = 1.909 decimal
RUIN_PROTECTION_FLOOR = Decimal("0.01")  # never recommend < 1% of bankroll

class SignalType(str, Enum):
    WIN_PROB_THRESHOLD = "WIN_PROB_THRESHOLD"
    MOMENTUM_SHIFT = "MOMENTUM_SHIFT"
    PROJECTION_UPDATE = "PROJECTION_UPDATE"
    INJURY_IMPACT = "INJURY_IMPACT"
    REFEREE_BIAS = "REFEREE_BIAS"
    FATIGUE_EDGE = "FATIGUE_EDGE"

TIER_CONFIDENCE_MULTIPLIER = {
    1: Decimal("1.00"),   # Tier 1: full Kelly
    2: Decimal("0.75"),   # Tier 2: 75% Kelly (lower confidence)
    3: Decimal("0.50"),   # Tier 3: half Kelly (informational)
}

@dataclass
class EdgeEstimate:
    signal_type: str
    tier: int
    epoch_win_probability: Decimal
    implied_probability: Decimal
    raw_edge: Decimal
    historical_hit_rate: Optional[Decimal]
    sample_count: int
    blended_edge: Decimal
    confidence: str  # "HIGH", "MEDIUM", "LOW", "INSUFFICIENT_DATA"

@dataclass
class KellyRecommendation:
    signal_type: str
    tier: int
    edge_estimate: EdgeEstimate
    bankroll: Decimal
    decimal_odds: Decimal
    full_kelly_fraction: Decimal
    half_kelly_fraction: Decimal
    recommended_fraction: Decimal   # tier-adjusted half-Kelly
    recommended_bet_size: Decimal   # in dollars
    expected_value_per_dollar: Decimal
    causal_context: Optional[str]
    reasoning: str

def american_to_decimal(american_odds: int) -> Decimal:
    """Convert American odds to decimal odds."""
    if american_odds > 0:
        return Decimal(str(american_odds)) / Decimal("100") + Decimal("1")
    else:
        return Decimal("100") / Decimal(str(abs(american_odds))) + Decimal("1")

def decimal_to_implied_probability(decimal_odds: Decimal) -> Decimal:
    """Convert decimal odds to implied probability (with vig)."""
    return (Decimal("1") / decimal_odds).quantize(
        Decimal("0.0001"), rounding=ROUND_HALF_UP
    )

def compute_full_kelly(
    win_probability: Decimal,
    decimal_odds: Decimal,
) -> Decimal:
    """
    Compute full Kelly fraction.
    f* = (bp - q) / b
    Capped at MAX_KELLY_FRACTION.
    Returns 0 if edge is negative.
    """
    b = decimal_odds - Decimal("1")
    p = win_probability
    q = Decimal("1") - p
    if b <= 0:
        return Decimal("0")
    kelly = (b * p - q) / b
    if kelly <= 0:
        return Decimal("0")
    return min(kelly, MAX_KELLY_FRACTION).quantize(
        Decimal("0.0001"), rounding=ROUND_HALF_UP
    )

def load_signal_history(
    journal_path: str = "data/betting_journal.jsonl",
) -> Dict[str, List[dict]]:
    """
    Load historical signal outcomes from betting journal.
    Returns dict of signal_type → list of outcome records.
    """
    history: Dict[str, List[dict]] = {}
    path = Path(journal_path)
    if not path.exists():
        return history
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                if record.get("outcome") is None:
                    continue  # unresolved bet
                signal_type = record.get("signal_type", "UNKNOWN")
                if signal_type not in history:
                    history[signal_type] = []
                history[signal_type].append(record)
    except Exception as e:
        print(f"Warning loading signal history: {e}")
    return history

def compute_edge_estimate(
    signal_type: str,
    tier: int,
    epoch_win_probability: float,
    decimal_odds: float = 1.909,
    journal_path: str = "data/betting_journal.jsonl",
) -> EdgeEstimate:
    """
    Compute blended edge estimate for a signal.
    Blends prior (30%) with historical hit rate (70%) when
    sufficient samples exist. Falls back to prior-only otherwise.
    """
    wp = Decimal(str(epoch_win_probability))
    odds = Decimal(str(decimal_odds))
    implied_prob = decimal_to_implied_probability(odds)
    raw_edge = (wp - implied_prob).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

    history = load_signal_history(journal_path)
    signal_history = history.get(signal_type, [])
    sample_count = len(signal_history)

    historical_hit_rate = None
    if sample_count >= MIN_SAMPLES_FOR_HISTORICAL:
        wins = sum(1 for r in signal_history if r.get("outcome") == "WIN")
        historical_hit_rate = Decimal(str(wins / sample_count)).quantize(
            Decimal("0.0001"), rounding=ROUND_HALF_UP
        )
        historical_implied = Decimal(
            str(sum(
                1 / float(r.get("decimal_odds", 1.909))
                for r in signal_history
            ) / sample_count)
        )
        historical_edge = historical_hit_rate - historical_implied
        blended_edge = (
            PRIOR_WEIGHT * raw_edge + HISTORICAL_WEIGHT * historical_edge
        ).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
        confidence = (
            "HIGH" if sample_count >= 100 and blended_edge > Decimal("0.03")
            else "MEDIUM" if sample_count >= MIN_SAMPLES_FOR_HISTORICAL
            else "LOW"
        )
    else:
        blended_edge = raw_edge
        confidence = "INSUFFICIENT_DATA" if sample_count < 10 else "LOW"

    return EdgeEstimate(
        signal_type=signal_type,
        tier=tier,
        epoch_win_probability=wp,
        implied_probability=implied_prob,
        raw_edge=raw_edge,
        historical_hit_rate=historical_hit_rate,
        sample_count=sample_count,
        blended_edge=blended_edge,
        confidence=confidence,
    )

def compute_kelly_recommendation(
    signal_type: str,
    tier: int,
    epoch_win_probability: float,
    bankroll: float,
    decimal_odds: float = 1.909,
    causal_context: Optional[str] = None,
    journal_path: str = "data/betting_journal.jsonl",
) -> KellyRecommendation:
    """
    Main entry point. Compute full Kelly recommendation for a signal.
    Returns recommendation with bet size, EV, and reasoning.
    """
    bankroll_d = Decimal(str(bankroll))
    odds_d = Decimal(str(decimal_odds))

    edge = compute_edge_estimate(
        signal_type, tier, epoch_win_probability, decimal_odds, journal_path
    )

    if edge.blended_edge <= MIN_EDGE_TO_BET:
        return KellyRecommendation(
            signal_type=signal_type,
            tier=tier,
            edge_estimate=edge,
            bankroll=bankroll_d,
            decimal_odds=odds_d,
            full_kelly_fraction=Decimal("0"),
            half_kelly_fraction=Decimal("0"),
            recommended_fraction=Decimal("0"),
            recommended_bet_size=Decimal("0"),
            expected_value_per_dollar=Decimal("0"),
            causal_context=causal_context,
            reasoning=f"No bet — edge {edge.blended_edge:.4f} below minimum threshold {MIN_EDGE_TO_BET}",
        )

    wp = Decimal(str(epoch_win_probability))
    full_kelly = compute_full_kelly(wp, odds_d)
    half_kelly = (full_kelly / HALF_KELLY_DIVISOR).quantize(
        Decimal("0.0001"), rounding=ROUND_HALF_UP
    )

    # Tier confidence adjustment
    tier_multiplier = TIER_CONFIDENCE_MULTIPLIER.get(tier, Decimal("0.50"))
    recommended_fraction = (half_kelly * tier_multiplier).quantize(
        Decimal("0.0001"), rounding=ROUND_HALF_UP
    )
    recommended_fraction = max(recommended_fraction, RUIN_PROTECTION_FLOOR)
    recommended_fraction = min(recommended_fraction, MAX_KELLY_FRACTION)

    recommended_bet = (bankroll_d * recommended_fraction).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )

    # Expected value per dollar risked
    b = odds_d - Decimal("1")
    ev = (b * wp - (Decimal("1") - wp)).quantize(
        Decimal("0.0001"), rounding=ROUND_HALF_UP
    )

    reasoning_parts = [
        f"Tier {tier} signal | Edge: {edge.blended_edge:+.4f}",
        f"Win probability: {float(wp):.1%} vs implied {float(edge.implied_probability):.1%}",
        f"Full Kelly: {float(full_kelly):.2%} → Half-Kelly: {float(half_kelly):.2%}",
        f"Tier {tier} adjustment ({float(tier_multiplier):.0%}): {float(recommended_fraction):.2%} of bankroll",
        f"Recommended bet: ${float(recommended_bet):,.2f} on ${float(bankroll_d):,.2f} bankroll",
        f"Expected value: {float(ev):+.4f} per dollar risked",
        f"Sample confidence: {edge.confidence} ({edge.sample_count} historical samples)",
    ]
    if causal_context:
        reasoning_parts.append(f"Causal context: {causal_context}")

    return KellyRecommendation(
        signal_type=signal_type,
        tier=tier,
        edge_estimate=edge,
        bankroll=bankroll_d,
        decimal_odds=odds_d,
        full_kelly_fraction=full_kelly,
        half_kelly_fraction=half_kelly,
        recommended_fraction=recommended_fraction,
        recommended_bet_size=recommended_bet,
        expected_value_per_dollar=ev,
        causal_context=causal_context,
        reasoning=" | ".join(reasoning_parts),
    )

def serialize_recommendation(rec: KellyRecommendation) -> dict:
    """Serialize KellyRecommendation to JSON-safe dict."""
    return {
        "signal_type": rec.signal_type,
        "tier": rec.tier,
        "bankroll": float(rec.bankroll),
        "decimal_odds": float(rec.decimal_odds),
        "full_kelly_fraction": float(rec.full_kelly_fraction),
        "half_kelly_fraction": float(rec.half_kelly_fraction),
        "recommended_fraction": float(rec.recommended_fraction),
        "recommended_bet_size": float(rec.recommended_bet_size),
        "expected_value_per_dollar": float(rec.expected_value_per_dollar),
        "causal_context": rec.causal_context,
        "reasoning": rec.reasoning,
        "edge": {
            "raw_edge": float(rec.edge_estimate.raw_edge),
            "blended_edge": float(rec.edge_estimate.blended_edge),
            "confidence": rec.edge_estimate.confidence,
            "sample_count": rec.edge_estimate.sample_count,
            "historical_hit_rate": (
                float(rec.edge_estimate.historical_hit_rate)
                if rec.edge_estimate.historical_hit_rate else None
            ),
        },
    }
