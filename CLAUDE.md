# EPOCH ENGINE — Session Context
GitHub: private repo (epoch-engine)
Last session: Phase 10 active — state logger enriched, signals hardened
Current status: All 3 priorities complete. Ready for advanced systems.
Next: System A (Live WebSocket Dashboard) → System B (Knowledge Graph + GNN) → System C (LLM Reports)
Roadmap: See `docs/ROADMAP.md` for full strategic plan

# EPOCH ENGINE — PROJECT BIBLE

> Claude Code reads this file automatically at the start of every session.
> This is the single source of truth for what you are building.

## What This Is

Epoch Engine is an NBA Digital Twin — a system that converts real NBA statistics
into precise byte values for the NBA 2K14 `.ROS` binary roster file, then runs
Monte Carlo simulations against those rosters, and ultimately powers a
prediction/signal product for sports analytics.

## Phases Completed

| Phase | Name | Key Milestone |
|---|---|---|
| 1 | Binary Engine | 1,664 players parsed from `.ROS` format |
| 2 | Translation Matrix | Real NBA stats → `.ROS` byte values |
| 3 | Full Warriors Roster | Curry POC, stress-tested boundary records + CRC |
| 4 | Rostra V1 Web UI | Browse, compare, download roster files |
| 5 | Headless Simulation | Live memory reads via `pymem` |
| 6 | The Signal | Win probability + divergence alerts |
| 7 | 12 ML Intelligence Systems | Calibration, pace, clutch, momentum, spreads |
| 8 | Maximum Accuracy | RandomForest AUC 0.857 |
| 9 | Real Outcome Tracking | Team differentiation, live predictions |

**Phase 10 [ACTIVE]**: Calibration tuning, signal hardening, state logger enrichment.
Goal: production-ready for Step 13 private beta (50 bettors/analysts).

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

## Architecture Decisions

- **Language**: Python 3.11+
- **API**: FastAPI (`src/api/main.py`) — serves Rostra V1 + prediction endpoints
- **Frontend**: React + Vite + Tailwind (`src/frontend/`)
- **Dependencies**: `struct` (stdlib), `zlib` (stdlib), `bitarray`, `numpy`, `pymem`, `psutil`, `pytest`, `hypothesis`, `scikit-learn`, `fastapi`
- **CV**: YOLOv8 (`yolov8x.pt`) for vision-based data extraction
- **No external CRC library** — pure `zlib.crc32` from stdlib
- **Pure functions over classes** — the engine core is functional, not OOP
- **All field indices are constants** — no magic numbers anywhere in the codebase

## File Map

```
Epoch/
├── CLAUDE.md                          ← YOU ARE HERE — project bible
├── README.md                          ← Public-facing overview
├── requirements.txt                   ← Python dependencies
├── yolov8x.pt                         ← YOLOv8 model weights
│
├── data/                              ← All runtime data
│   ├── roster.ros                     ← Base .ROS file
│   ├── default-ros.ROS                ← Vanilla .ROS backup
│   ├── {team}_poc.ros                 ← Per-team modified rosters (30 teams)
│   ├── {team}_roster.json             ← Per-team player mappings
│   ├── calibration_history.jsonl      ← Prediction vs outcome log
│   ├── pipeline_report.json           ← Last pipeline run report
│   ├── nba_history.db                 ← SQLite historical stats
│   ├── predictions/                   ← Daily prediction JSONL logs
│   ├── signal_alerts/                 ← Daily signal alert JSONL logs
│   ├── sim_logs/                      ← Simulation state JSONL logs
│   ├── batch_logs/                    ← Batch simulation results
│   ├── cache/                         ← API response caches
│   ├── models/                        ← Trained ML model pickles
│   └── synthetic/                     ← Generated synthetic datasets
│
├── src/
│   ├── binary/                        ← CORE: .ROS read/write engine
│   │   ├── constants.py               ← Offsets, codecs, CRC, labels
│   │   ├── ros_reader.py              ← Read + validate + parse
│   │   └── ros_writer.py              ← Write + CRC recalc + save
│   │
│   ├── intelligence/                  ← Analytical brain
│   │   ├── fatigue_model.py           ← Rest days, travel, altitude
│   │   ├── momentum.py                ← In-game momentum tracking
│   │   ├── pregame_predictor.py       ← Pre-game win probability
│   │   ├── referee_model.py           ← Referee crew bias/foul rates
│   │   ├── signal_alerts.py           ← Alert engine (Tier 1-3 signals)
│   │   ├── translation_matrix.py      ← Real stats → .ROS byte formulas
│   │   └── win_probability.py         ← Live win probability model
│   │
│   ├── ml/                            ← ML models & analytics
│   │   ├── aggregator.py              ← Ensemble vote aggregation
│   │   ├── calibration.py             ← Platt scaling + Brier score
│   │   ├── clutch_detector.py         ← Clutch situation detection
│   │   ├── comeback_engine.py         ← Comeback probability
│   │   ├── data_generator.py          ← Synthetic training data
│   │   ├── game_script.py             ← Game script classification
│   │   ├── momentum_reversal.py       ← Momentum shift detection
│   │   ├── pace_classifier.py         ← Pace classification
│   │   ├── quarter_trajectory.py      ← Quarter-by-quarter modeling
│   │   ├── scoring_run_predictor.py   ← Scoring run forecasting
│   │   ├── spread_calculator.py       ← Point spread estimation
│   │   ├── total_forecaster.py        ← Over/under forecasting
│   │   └── value_detector.py          ← Market value edge detection
│   │
│   ├── simulation/                    ← Headless sim pipeline
│   │   ├── action_recorder.py         ← Game action capture
│   │   ├── headless_runner.py         ← Orchestrates sim sessions
│   │   ├── memory_reader.py           ← pymem game state reads
│   │   ├── process_manager.py         ← Game process lifecycle
│   │   ├── run_simulation.py          ← Monte Carlo batch runner
│   │   └── state_logger.py            ← JSONL state capture ⚠️ NEEDS ENRICHMENT
│   │
│   ├── pipeline/                      ← Data ingestion
│   │   ├── full_league_pipeline.py    ← All 30 teams automation
│   │   ├── historical_ingestion.py    ← Historical stats import
│   │   ├── results_ingestion.py       ← Real game outcome tracking
│   │   ├── schedule_fetcher.py        ← NBA schedule API
│   │   └── ingest/
│   │       └── nba_api_client.py      ← nba_api wrapper
│   │
│   ├── api/                           ← Backend API
│   │   └── main.py                    ← FastAPI: roster, signal, prediction endpoints
│   │
│   ├── frontend/                      ← Rostra V1 Web UI
│   │   ├── src/                       ← React components
│   │   ├── vite.config.js
│   │   └── tailwind.config.js
│   │
│   └── vision/                        ← Computer vision layer
│       ├── court_analyzer.py          ← Court detection + mapping
│       ├── player_tracker.py          ← Player position tracking
│       └── vision_bridge.py           ← Vision → engine data bridge
│
├── tests/                             ← pytest + hypothesis suite
│   ├── test_binary.py                 ← CRC, codec, nibble-shift round-trips
│   ├── test_translation.py            ← Translation Matrix validation
│   ├── test_ml.py                     ← ML model unit tests
│   ├── test_signal.py                 ← Signal alert logic tests
│   ├── test_simulation.py             ← Simulation pipeline tests
│   ├── test_vision.py                 ← Vision module tests
│   ├── test_phase8.py                 ← Phase 8 accuracy tests
│   ├── test_phase9.py                 ← Phase 9 outcome tracking tests
│   ├── test_phase10.py                ← Phase 10 calibration tests
│   └── test_phase11.py                ← Phase 11 integration tests
│
├── scripts/                           ← Utility & POC scripts
│   ├── curry_proof_of_concept.py      ← Original Curry POC
│   ├── warriors_full_roster.py        ← Full Warriors roster script
│   ├── run_all_tests.py               ← Test runner
│   ├── check_pipeline_report.py       ← Pipeline health check
│   └── verify_accuracy_api.py         ← API accuracy verification
│
├── specs/                             ← Binary format specs
│   ├── NBA2K14_Master_Spec_S1-S51_COMPLETE.docx
│   └── prompts.md                     ← 10 Claude Opus 4.6 prompt templates
│
└── docs/                              ← System documentation
    ├── EpochEngine_MasterDocument.docx
    ├── EpochEngine_AdvancedSystems.docx
    └── EpochEngine_TechStack.docx
```

## API Endpoints (FastAPI)

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/roster/{team}` | GET | Compare before/after player attributes |
| `/api/player/{name}` | GET | Individual player attribute diff |
| `/api/download/{team}` | GET | Download team's `.ROS` file |
| `/api/signal/current` | GET | Live simulation signal (10s staleness check) |
| `/api/accuracy` | GET | Brier score + calibration report |
| `/api/predictions/today` | GET | Today's game predictions |
| `/api/predictions/history` | GET | All historical predictions + metrics |
| `/api/schedule` | GET | Today's NBA schedule |

**Run**: `uvicorn src.api.main:app --reload`

## Rules For Every Session

1. **Never write magic numbers** — import from `constants.py`
2. **Never skip CRC recalculation** — every write path must call `recalculate_crc()`
3. **Never write to tendency indices 57–68** — these are engine-internal
4. **Always handle boundary records** — check if EVEN+ODD share TeamID byte
5. **Always validate ranges** — skill tier 0–13, tendency 0–99, hot zone 0–3
6. **Test against the real .ROS file** when available at `data/roster.ros`
7. **Stat encoding cap is 255** (not 222) — supports modded players up to rating 110
