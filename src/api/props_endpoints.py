from fastapi import APIRouter, Header, HTTPException
from typing import Optional
from src.api.auth import get_user_from_token, require_tier, check_and_increment_api_calls

router = APIRouter(prefix="/api/props", tags=["props"])

def _require_signal_tier(authorization: Optional[str]) -> str:
    """Extract user from Bearer token and verify SIGNAL tier minimum."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    token = authorization.replace("Bearer ", "")
    user = get_user_from_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    if not require_tier("SIGNAL", user.tier):
        raise HTTPException(status_code=403, detail="SIGNAL tier or above required")
    if not check_and_increment_api_calls(user.user_id):
        raise HTTPException(status_code=429, detail="Daily API call limit reached")
    return user.user_id

@router.get("/player/{player_id}")
async def get_player_props(
    player_id: str,
    prop_type: str = "POINTS",
    prop_line: float = 22.5,
    team: str = "GSW",
    causal_usage_factor: float = 1.0,
    causal_injury_factor: float = 1.0,
    authorization: Optional[str] = Header(None),
):
    """
    Get prop distribution for a player.
    Requires SIGNAL tier.
    """
    _require_signal_tier(authorization)
    from src.simulation.quantum_roster import _build_synthetic_quantum_roster
    from src.intelligence.prop_model import compute_prop_distribution, PropType
    try:
        pt = PropType(prop_type.upper())
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid prop_type: {prop_type}")

    roster = _build_synthetic_quantum_roster(team)
    if player_id not in roster.players:
        raise HTTPException(status_code=404, detail=f"Player {player_id} not found on {team}")

    player_dist = roster.players[player_id]
    result = compute_prop_distribution(
        player_id=player_id,
        player_name=player_dist.player_name,
        player_dist=player_dist,
        prop_type=pt,
        prop_line=prop_line,
        n_samples=1000,
        causal_injury_factor=causal_injury_factor,
        causal_usage_factor=causal_usage_factor,
    )
    return {
        "player_id": result.player_id,
        "player_name": result.player_name,
        "prop_type": result.prop_type,
        "prop_line": result.prop_line,
        "over_probability": result.over_probability,
        "under_probability": result.under_probability,
        "distribution": result.distribution,
        "mean_projection": result.mean_projection,
        "edge_vs_line": result.edge_vs_line,
        "confidence": result.confidence,
        "causal_factors": result.causal_factors,
    }

@router.get("/kelly/{signal_type}")
async def get_kelly_recommendation(
    signal_type: str,
    tier: int = 1,
    win_probability: float = 0.62,
    bankroll: float = 10000.0,
    american_odds: int = -110,
    causal_context: Optional[str] = None,
    authorization: Optional[str] = Header(None),
):
    """
    Get Kelly Criterion recommendation for a signal.
    Requires SIGNAL tier.
    """
    _require_signal_tier(authorization)
    from src.intelligence.kelly_criterion import (
        compute_kelly_recommendation,
        serialize_recommendation,
        american_to_decimal,
    )
    from decimal import Decimal
    decimal_odds = float(american_to_decimal(american_odds))
    rec = compute_kelly_recommendation(
        signal_type=signal_type,
        tier=tier,
        epoch_win_probability=win_probability,
        bankroll=bankroll,
        decimal_odds=decimal_odds,
        causal_context=causal_context,
    )
    return serialize_recommendation(rec)

@router.get("/journal/{user_id}/profile")
async def get_edge_profile(
    user_id: str,
    authorization: Optional[str] = Header(None),
):
    """
    Get personalized edge profile for a user.
    Requires SIGNAL tier.
    """
    _require_signal_tier(authorization)
    from src.api.betting_journal import compute_edge_profile
    return compute_edge_profile(user_id)
