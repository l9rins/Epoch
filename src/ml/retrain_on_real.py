"""
retrain_on_real.py — Epoch Engine
====================================
1. Retrains WinProbabilityModel on real game snapshots from data/real/games_2024.jsonl.
2. Rebuilds the ensemble model by engineering features from the same real game data.
"""

import os
import sys
import json
import logging
import numpy as np
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.intelligence.win_probability import WinProbabilityModel
from src.ml.ensemble_model import train_ensemble
from src.ml.feature_engineer import build_feature_matrix, engineer_features

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("retrain_on_real")

REAL_DATA_PATH = Path("data/real/games_2024.jsonl")

def enrich_game_data(games: list[dict]) -> list[dict]:
    """
    Enrich raw game records with fields needed for feature engineering:
    - home_win (0 or 1)
    - home_rest_days, away_rest_days
    - home_win_pct_prior, away_win_pct_prior
    - home_last_5_wins, away_last_5_wins
    - home_ortg, home_drtg (proxies from points)
    """
    log.info("Enriching %d games for ensemble training...", len(games))
    
    # Sort by date
    games.sort(key=lambda x: x["game_date"])
    
    team_history = {} # team: list of game dates and results
    
    enriched = []
    for g in games:
        date = datetime.strptime(g["game_date"], "%Y-%m-%d")
        home = g["home_team"]
        away = g["away_team"]
        
        # Home won?
        home_won = 1 if g["final_home"] > g["final_away"] else 0
        
        # Calculate rest and win pct
        def get_team_stats(team, current_date):
            history = team_history.get(team, [])
            if not history:
                return 2, 0.5, 2 # rest, win_pct, last5
            
            # Rest days
            last_date = history[-1]["date"]
            rest = min(7, (current_date - last_date).days)
            
            # Win pct prior
            wins = sum(1 for h in history if h["won"])
            win_pct = wins / len(history)
            
            # Last 5
            last5_wins = sum(1 for h in history[-5:] if h["won"])
            
            return rest, win_pct, last5_wins

        home_rest, home_win_pct, home_l5 = get_team_stats(home, date)
        away_rest, away_win_pct, away_l5 = get_team_stats(away, date)
        
        # Create enriched record
        eg = g.copy()
        eg.update({
            "home_win": home_won,
            "home_rest_days": home_rest,
            "away_rest_days": away_rest,
            "home_win_pct_prior": home_win_pct,
            "away_win_pct_prior": away_win_pct,
            "home_last_5_wins": home_l5,
            "away_last_5_wins": away_l5,
            "home_is_b2b": home_rest == 1,
            "away_is_b2b": away_rest == 1,
            # Proxies for ratings
            "home_ortg": 114.0 + (home_win_pct - 0.5) * 10,
            "away_ortg": 114.0 + (away_win_pct - 0.5) * 10,
            "home_drtg": 114.0 - (home_win_pct - 0.5) * 10,
            "away_drtg": 114.0 - (away_win_pct - 0.5) * 10,
            "home_pace": 99.8,
            "away_pace": 99.8,
            "home_altitude_ft": 500, # default
        })
        enriched.append(eg)
        
        # Update history
        team_history.setdefault(home, []).append({"date": date, "won": home_won == 1})
        team_history.setdefault(away, []).append({"date": date, "won": home_won == 0})
        
    return enriched

def main():
    if not REAL_DATA_PATH.exists():
        log.error(f"Data file not found: {REAL_DATA_PATH}. Please run real_data_pipeline first.")
        return

    # --- Step 1: Retrain WinProbabilityModel ---
    log.info("Step 1: Retraining WinProbabilityModel on real data snapshots...")
    WinProbabilityModel.TRAIN_DATA = REAL_DATA_PATH
    WinProbabilityModel.train()

    # --- Step 2: Retrain Ensemble ---
    log.info("Step 2: Preparing data for Ensemble retraining...")
    raw_games = []
    with open(REAL_DATA_PATH) as f:
        for line in f:
            if line.strip():
                raw_games.append(json.loads(line))
    
    enriched_games = enrich_game_data(raw_games)
    
    log.info("Building feature matrix (Group A-F features)...")
    X, y = build_feature_matrix(enriched_games)
    
    log.info("Training ensemble (RF + XGBoost/GBM)...")
    meta = train_ensemble(X, y)
    
    log.info("Retraining complete!")
    log.info(f"Ensemble AUC on real data: {meta['ensemble_auc']:.4f}")
    log.info(f"Ensemble Brier score: {meta['ensemble_brier']:.4f}")

if __name__ == "__main__":
    main()
