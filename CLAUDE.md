# EPOCH ENGINE — Session Context
GitHub: l9rins/epoch (private)
Last updated: 2026-03-17 — sim layer retired, frontend rebuilt, requirements audited
Current status: Phase 10 active. Platform UI (Analyst / Bettor / Roster) built.
Next: Wire frontend to live API → odds fetcher → WebSocket signal feed

# EPOCH ENGINE — PROJECT BIBLE

> Claude Code reads this file automatically at the start of every session.
> This is the single source of truth for what you are building.
> Deep domain knowledge lives in /docs/vault/. Retired systems in /docs/vault/graveyard.md.

---

## What This Is

Epoch Engine is an NBA prediction and intelligence platform. It ingests real NBA
statistics, syncs them into NBA 2K14 `.ROS` binary roster files (for gamers),
and powers a three-mode prediction product — Analyst, Bettor, Roster — through
causal ML, fatigue modeling, GNN graph intelligence, and live signal detection.

---

## Phases Completed

| Phase | Name | Key Milestone |
|---|---|---|
| 1 | Binary Engine | 1,664 players parsed from `.ROS` format |
| 2 | Translation Matrix | Real NBA stats → `.ROS` byte values |
| 3 | Full Warriors Roster | Curry POC, stress-tested boundary records + CRC |
| 4 | Rostra V1 Web UI | Browse, compare, download roster files |
| 5 | Headless Simulation | **RETIRED** — see `/docs/vault/graveyard.md` |
| 6 | The Signal | Win probability + divergence alerts |
| 7 | 12 ML Intelligence Systems | Calibration, pace, clutch, momentum, spreads |
| 8 | Maximum Accuracy | RandomForest AUC 0.857 |
| 9 | Real Outcome Tracking | Team differentiation, live predictions |
| 10 | **[ACTIVE]** | Calibration tuning, signal hardening, platform UI |

---

## Critical Binary Format Facts (.ROS)

| Property | Value |
|---|---|
| File size | ~2.67 MB |
| CRC | `zlib.crc32(data[4:]) & 0xFFFFFFFF`, stored Big-Endian uint32 at offset `0x0000` |
| Primary records | 832 records × 2 players each = **1,664 total players** |
| EVEN players | Standard layout |
| ODD players | **Nibble-shifted**, data starts at offset `+0x1C7` within record |
| Skill codec | `tier = floor(raw_value / 3)` → rating = `(tier × 3) + 25` |
| Skill fields | 42 total, tier 0–13 (ratings 25–64) |
| Tendency fields | 57 total, tier 0–6 (raw 0–99 stored, NOT encoded) |
| Internal tendencies | Indices 57–68 are engine-internal — **never write to these** |
| Hot zones | 14 zones, 2-bit packed (Cold=0, Neutral=1, Hot=2, Burned=3) |
| Height/Weight | Float32 Big-Endian at `+0x000` / `+0x004` |
| TeamID | Single byte at `+0x00B` |
| BirthDate | Bit-packed starting at bit 149 |
| Name String Pool | UTF-16 LE at `0x25ED40`–`0x28B7DF` |
| TOC | 40 embedded CSVs at `0x0020`–`0x01FF` |
| Boundary records | 19 records where EVEN+ODD share a single TeamID byte |
| Signature skills | 5 slots per player, 41 valid entries (2K14 RED MC Enums order) |
| Sig skill stubs 41-44 | Assist Bonus, Off Awareness Bonus, Def Awareness Bonus, Attribute Penalty |
| Stat encoding cap | **255** (not 222) — supports modded players up to rating 110 |

---

## Architecture

- **Language**: Python 3.11+
- **API**: FastAPI (`src/api/main.py`) — async, WebSocket, Stripe
- **Frontend**: React + Vite (`src/frontend/`) — Analyst / Bettor / Roster modes
- **ML**: scikit-learn, PyTorch, XGBoost, causal DAGs
- **GNN**: torch-geometric (optional, graceful fallback if absent)
- **LLM**: Anthropic Claude (`claude-sonnet-4-20250514`) + Groq fallback
- **Binary**: `struct` + `zlib` stdlib only — no external CRC library
- **Vision**: OpenCV + YOLOv8 (`yolov8x.pt`)
- **Cache**: Redis + aiosqlite
- **Odds**: The Odds API (`src/pipeline/odds_fetcher.py`) — NBA moneylines/spreads/totals
- **Pure functions over classes** — engine core is functional, not OOP
- **All field indices are constants** — no magic numbers anywhere

---

## File Map

```
epoch/
├── CLAUDE.md                              ← YOU ARE HERE
├── README.md
├── requirements.txt                       ← Audited minimal (~45 packages)
├── Dockerfile
├── railway.toml
├── .env.example
│
├── data/
│   ├── roster.ros                         ← Base .ROS file
│   ├── curry_poc.ros                      ← Curry POC roster
│   ├── {team}_poc.ros                     ← Per-team modified rosters
│   ├── {team}_roster.json                 ← Per-team player mappings
│   ├── nba_history.db                     ← SQLite historical stats
│   ├── cache/                             ← API response caches
│   ├── predictions/                       ← Daily prediction JSONL logs
│   ├── real/                              ← Real game outcomes 2020-2024
│   ├── synthetic/                         ← Generated synthetic datasets
│   └── models/                            ← Trained ML model pickles
│
├── src/
│   ├── api/
│   │   ├── main.py                        ← FastAPI: all endpoints + WebSocket
│   │   ├── websocket.py                   ← WebSocket connection manager
│   │   ├── auth.py / auth_endpoints.py    ← JWT auth
│   │   ├── stripe_endpoints.py            ← Stripe monetization
│   │   ├── public_endpoints.py            ← Public accuracy dashboard
│   │   ├── intelligence_endpoints.py      ← Causal + graph endpoints
│   │   ├── props_endpoints.py             ← Player props
│   │   └── betting_journal.py             ← Journal tracking
│   │
│   ├── binary/                            ← CORE: .ROS read/write engine
│   │   ├── constants.py                   ← Offsets, codecs, CRC, labels
│   │   ├── ros_reader.py                  ← Read + validate + parse
│   │   └── ros_writer.py                  ← Write + CRC recalc + save
│   │
│   ├── intelligence/
│   │   ├── fatigue_model.py
│   │   ├── momentum.py
│   │   ├── pregame_predictor.py           ← Pre-game ensemble predictor
│   │   ├── referee_model.py
│   │   ├── signal_alerts.py               ← Alert engine (Tier 1-3)
│   │   ├── signal_validator.py
│   │   ├── translation_matrix.py          ← Real stats → .ROS byte formulas
│   │   ├── win_probability.py
│   │   ├── causal_dag.py
│   │   ├── causal_learner.py
│   │   ├── causal_explainer.py            ← Claude-powered scouting reports
│   │   ├── adversarial_network.py
│   │   ├── injury_detector.py
│   │   ├── injury_matrix.py
│   │   ├── kelly_criterion.py
│   │   ├── player_embeddings.py
│   │   ├── prop_model.py
│   │   └── report_builder.py
│   │
│   ├── ml/
│   │   ├── aggregator.py                  ← Ensemble vote aggregation
│   │   ├── calibration.py                 ← Platt scaling + Brier score
│   │   ├── ensemble_model.py
│   │   ├── feature_engineer.py
│   │   ├── enrich_features.py
│   │   ├── real_data_pipeline.py
│   │   ├── retrainer.py                   ← Live retraining orchestrator
│   │   ├── upgrade_ensemble.py
│   │   ├── clutch_detector.py
│   │   ├── comeback_engine.py
│   │   ├── game_script.py
│   │   ├── momentum_reversal.py
│   │   ├── pace_classifier.py
│   │   ├── quarter_trajectory.py
│   │   ├── scoring_run_predictor.py
│   │   ├── spread_calculator.py
│   │   ├── total_forecaster.py
│   │   └── value_detector.py
│   │
│   ├── graph/
│   │   ├── builder.py                     ← Knowledge graph builder
│   │   ├── schema.py
│   │   ├── features.py
│   │   ├── gnn_model.py                   ← GraphSAGE (torch-geometric)
│   │   └── gnn_prediction.py
│   │
│   ├── pipeline/
│   │   ├── full_league_pipeline.py        ← All 30 teams automation
│   │   ├── pipeline_orchestrator.py
│   │   ├── historical_ingestion.py
│   │   ├── results_ingestion.py
│   │   ├── schedule_fetcher.py
│   │   ├── fetch_player_logs.py
│   │   ├── bball_ref_fallback.py          ← Basketball Reference fallback
│   │   ├── health_monitor.py
│   │   ├── latency_tracker.py
│   │   ├── resource_audit.py
│   │   ├── state_logger.py
│   │   ├── calibration_seeder.py
│   │   ├── fatigue_seeder.py
│   │   ├── referee_seeder.py
│   │   ├── ingest_injury_history.py
│   │   ├── odds_fetcher.py                ← The Odds API (ADD THIS)
│   │   └── ingest/
│   │       └── nba_api_client.py
│   │
│   ├── frontend/
│   │   ├── index.html
│   │   ├── vite.config.js
│   │   ├── package.json
│   │   └── src/
│   │       ├── App.jsx
│   │       ├── main.jsx
│   │       ├── styles/globals.css
│   │       ├── lib/api.js
│   │       ├── hooks/useFetch.js
│   │       ├── hooks/useSignalFeed.js
│   │       └── components/
│   │           ├── shared/Topbar.jsx
│   │           ├── shared/UI.jsx
│   │           ├── analyst/AnalystMode.jsx
│   │           ├── analyst/ShotChart.jsx
│   │           ├── bettor/BettorMode.jsx
│   │           ├── roster/RosterMode.jsx
│   │           └── roster/CourtFormation.jsx
│   │
│   └── vision/
│       ├── court_analyzer.py
│       ├── player_tracker.py
│       ├── spacing_validator.py
│       └── vision_bridge.py
│
├── tests/                                 ← pytest suite (sim tests removed)
│
├── scripts/
│   ├── upgrade_ensemble.py
│
├── specs/
│   ├── NBA2K14_Master_Spec_S1-S51_COMPLETE.docx
│   └── prompts.md
│
└── docs/
    ├── ROADMAP.md
    ├── EpochEngine_MasterDocument.docx
    ├── EpochEngine_AdvancedSystems.docx
    ├── EpochEngine_TechStack.docx
    └── vault/
        ├── binary.md
        ├── pipeline.md
        ├── intelligence.md
        ├── ml.md
        ├── data-sources.md
        └── graveyard.md
```

---

## API Endpoints

| Endpoint | Method | Purpose |
|---|---|---|
| `/health` | GET | Deployment health check |
| `/api/pipeline/health` | GET | Pipeline staleness + cascade multipliers |
| `/api/roster/{team}` | GET | Before/after player attribute diff |
| `/api/player/{name}` | GET | Individual player diff |
| `/api/download/{team}` | GET | Download team `.ROS` file |
| `/api/predict` | POST | Full ensemble prediction + Kelly sizing |
| `/api/signal/current` | GET | Current signal (10s staleness check) |
| `/api/signal/validation` | GET | Signal validation history |
| `/api/accuracy` | GET | Brier score + calibration report |
| `/api/predictions/today` | GET | Today's predictions |
| `/api/predictions/history` | GET | All historical predictions |
| `/api/schedule` | GET | Today's NBA schedule |
| `/api/odds/today` | GET | Live odds from The Odds API |
| `/api/report/{game_id}` | GET | Claude-powered scouting report |
| `/api/graph/{game_id}` | GET | GNN knowledge graph data |
| `/api/ensemble/meta` | GET | Ensemble model metadata |
| `/api/retrainer/run` | POST | Trigger live retraining |
| `/api/causal/weights` | GET | Causal DAG weights |
| `/ws/game/{game_id}` | WS | Live WebSocket feed |

**Run**: `uvicorn src.api.main:app --reload`

---

## Rules For Every Session

1. **Never write magic numbers** — import from `constants.py`
2. **Never skip CRC recalculation** — every write path must call `recalculate_crc()`
3. **Never write to tendency indices 57–68** — engine-internal
4. **Always handle boundary records** — check if EVEN+ODD share TeamID byte
5. **Always validate ranges** — skill tier 0–13, tendency 0–99, hot zone 0–3
6. **Test against real .ROS file** when available at `data/roster.ros`
7. **Stat encoding cap is 255** (not 222)
8. **All API endpoints must be async** — no blocking calls in FastAPI handlers
9. **Do not add simulation code** — retired permanently, see graveyard
10. **The Odds API key goes in `.env`** as `ODDS_API_KEY`
