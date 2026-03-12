from fastapi import APIRouter
from typing import Optional
import json
from pathlib import Path

router = APIRouter(prefix="/api/intelligence", tags=["intelligence"])

@router.get("/causal/{game_id}")
async def get_causal_inference(
    game_id: str,
    home_injury: float = 0.0,
    away_injury: float = 0.0,
):
    """
    Run causal inference for a game.
    Params: home_injury/away_injury = 0.0 (healthy) to 1.0 (star player out)
    """
    from src.intelligence.causal_dag import (
        run_causal_inference, CausalNode, CausalState
    )
    home_interventions = {}
    away_interventions = {}
    if home_injury > 0:
        home_interventions[CausalNode.PLAYER_HEALTH] = 1.0 - home_injury
    if away_injury > 0:
        away_interventions[CausalNode.PLAYER_HEALTH] = 1.0 - away_injury

    result = run_causal_inference(home_interventions, away_interventions)
    return {
        "game_id": game_id,
        "win_probability_adjustment": result.win_probability_adjustment,
        "causal_chain": result.causal_chain,
        "mechanism": result.mechanism,
        "confidence": result.confidence,
        "home_state": result.home_state.to_dict(),
        "away_state": result.away_state.to_dict(),
    }

@router.get("/embeddings/similar/{player_id}")
async def get_similar_players(player_id: str, top_k: int = 5):
    """Find historically similar players using hyperdimensional embeddings."""
    from src.intelligence.player_embeddings import EmbeddingSpace
    space = EmbeddingSpace()
    if not space.embeddings:
        space.seed_with_defaults(50)
    similar = space.find_similar(player_id, top_k=top_k, exclude_same_season=False)
    return {
        "player_id": player_id,
        "similar_players": [
            {
                "player_id": e.player_id,
                "player_name": e.player_name,
                "team": e.team,
                "season": e.season,
                "similarity": round(score, 4),
            }
            for e, score in similar
        ]
    }

@router.get("/embeddings/chemistry")
async def get_lineup_chemistry(player_ids: str):
    """
    Compute lineup chemistry score from hyperdimensional embeddings.
    player_ids: comma-separated list of player_ids
    """
    from src.intelligence.player_embeddings import EmbeddingSpace
    ids = [p.strip() for p in player_ids.split(",")]
    space = EmbeddingSpace()
    if not space.embeddings:
        space.seed_with_defaults(50)
    result = space.compute_lineup_chemistry(ids)
    return {"player_ids": ids, "chemistry": result}

@router.post("/adversarial/train")
async def run_adversarial_training(cycles: int = 100):
    """
    Run adversarial training cycle.
    Oracle vs Adversary vs Market — eternal improvement loop.
    """
    from src.intelligence.adversarial_network import (
        build_adversarial_system,
        generate_synthetic_training_games,
        run_adversarial_training_cycle,
    )
    oracle, adversary, market = build_adversarial_system()
    games = generate_synthetic_training_games(300)
    result = run_adversarial_training_cycle(oracle, adversary, market, games, cycles=cycles)

    # Save trained Oracle weights
    weights_path = Path("data/models/oracle_weights.json")
    weights_path.parent.mkdir(parents=True, exist_ok=True)
    with open(weights_path, "w") as f:
        json.dump({
            "weights": result["final_weights"],
            "cycles": result["cycles_completed"],
            "final_error": result["final_avg_error"],
        }, f)

    return result

@router.get("/adversarial/report")
async def get_adversarial_report():
    """Get current Oracle training state and blind spot report."""
    weights_path = Path("data/models/oracle_weights.json")
    if not weights_path.exists():
        return {"status": "not_trained", "message": "Run POST /adversarial/train first"}
    with open(weights_path) as f:
        data = json.load(f)
    return {"status": "trained", "oracle_state": data}

@router.get("/quantum/{game_id}")
async def run_quantum_simulation(
    game_id: str,
    home_team: str = "GSW",
    away_team: str = "LAL",
    iterations: int = 1000,
):
    """
    Run true quantum Monte Carlo simulation.
    Each iteration samples player attributes from performance distributions.
    Returns full probability distribution, not a point estimate.
    """
    from src.simulation.quantum_roster import (
        build_quantum_roster_from_json,
        run_quantum_monte_carlo,
    )

    home_roster_path = f"data/{home_team.lower()}_roster.json"
    away_roster_path = f"data/{away_team.lower()}_roster.json"

    home_roster = build_quantum_roster_from_json(home_team, home_roster_path)
    away_roster = build_quantum_roster_from_json(away_team, away_roster_path)

    # Load fatigue context
    fatigue_path = Path("data/fatigue_context.json")
    fatigue_context = {}
    if fatigue_path.exists():
        import json
        with open(fatigue_path) as f:
            all_fatigue = json.load(f)
        from datetime import date
        today = str(date.today())
        home_key = f"{home_team}_{today}"
        away_key = f"{away_team}_{today}"
        home_fatigue_data = all_fatigue.get(home_key, {})
        away_fatigue_data = all_fatigue.get(away_key, {})
        if home_fatigue_data.get("is_back_to_back"):
            for pid in home_roster.players:
                fatigue_context[pid] = 0.92
        if away_fatigue_data.get("is_back_to_back"):
            for pid in away_roster.players:
                fatigue_context[pid] = 0.92

    result = run_quantum_monte_carlo(
        home_roster, away_roster,
        n_iterations=iterations,
        fatigue_context=fatigue_context,
    )
    result["game_id"] = game_id
    result["home_team"] = home_team
    result["away_team"] = away_team
    return result
