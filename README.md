# Epoch Engine
NBA Digital Twin Platform — reverse-engineered NBA 2K14 
physics engine with real NBA data pipeline and live 
betting intelligence.

## What It Does
- Reads live game state from NBA 2K14 memory
- Translates real 2024-25 NBA player stats into game attributes
- Runs 12 ML intelligence systems in real time
- Generates win probability, momentum, spread, and value bets

## Stack
Python 3.13, FastAPI, React, scikit-learn, pymem, nba_api

## Phases Complete
- Phase 1: Binary Engine (1,664 players parsed)
- Phase 2: Translation Matrix
- Phase 3: Full Warriors Roster
- Phase 4: Rostra V1 Web UI
- Phase 5: Headless Simulation (live memory reads)
- Phase 6: The Signal (win probability + alerts)
- Phase 7: 12 ML Intelligence Systems
- Phase 8: Maximum Accuracy (RandomForest AUC 0.857)
- Phase 9: Real Outcome Tracking

## Setup
pip install -r requirements.txt
uvicorn src.api.main:app --reload
