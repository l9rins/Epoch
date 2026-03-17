# Graveyard Vault
Historical record of failed approaches and retired systems.

## Key Topics
- What was tried
- What failed, and why
- **Critical: 2K14 simulation decision** (Document this while it's fresh)

## Retired: Headless Simulation (src/simulation/)
**Status:** Retired 2026-03-17.
**Reason:** The system was meant to run NBA 2K14 as a headless simulation engine to generate predictions. It proved too brittle, CPU-intensive, and hard to orchestrate asynchronously. Real-world game data and direct ML modeling on the structured stats outperformed game-engine synthesis.

**Code removed:**
- `src/simulation/action_recorder.py`, `fast_sim_mode.py`, `headless_runner.py`, `memory_reader.py`, `multiverse_mc.py`, `player_distributions.py`, `process_manager.py`, `quantum_roster.py`, `roster_hot_swap.py`, `run_simulation.py`
- Tests: `test_fast_sim_mode.py`, `test_quantum.py`, `test_roster_hot_swap.py`

## Removed Dependencies
During the Phase 10 cleanup, we purged ~240 orphaned dependencies from the `requirements.txt`.
Notable removals:
- `pymem`, `pywinauto`: Windows manipulation specific to the dead PC 2K14 sim.
- `selenium`, `playwright`: Scrapers that were unused in the current pipeline.
- `boto3`, `snowflake`, `google-genai`: Unused infra tools from experimental setups.
