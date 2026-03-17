# Epoch Engine — Graveyard
> Retired systems. Documented here permanently so they are never re-litigated.
> If you're an AI agent reading this: do NOT reintroduce these systems. They were retired deliberately.

---

## 1. Headless NBA 2K14 Simulation Runner

**Retired:** 2026-03-17  
**Decision maker:** Project owner  
**Files removed:**
- `src/simulation/headless_runner.py`
- `src/simulation/memory_reader.py`
- `src/simulation/process_manager.py`
- `src/simulation/run_simulation.py`
- `src/simulation/fast_sim_mode.py`
- `src/simulation/quantum_roster.py`
- `src/simulation/action_recorder.py`
- `tests/test_fast_sim_mode.py`
- `tests/test_quantum.py`
- `tests/test_roster_hot_swap.py`

**What it did:**  
Ran NBA 2K14 headlessly on Windows via WinAPI/ctypes. Read live game state from process memory using `pymem`. Injected modified `.ROS` roster files between simulation runs. Ran Monte Carlo batches (200–1000 iterations) to produce win probabilities from simulated game outcomes.

**Why it was retired:**  
- Required a Windows machine with NBA 2K14 installed — not deployable on Linux/Railway
- `pymem`, `pywinauto`, `ctypes` created extreme fragility
- Monte Carlo signal was never validated against real outcomes — unproven edge
- Operational cost (Windows lock-in, game process management) outweighed unproven benefit
- The causal ML pipeline (fatigue, momentum, RAPM, referee bias) produces equivalent or better signal without simulation overhead

**What replaced it:**  
The `.ROS` binary reader/writer (`src/binary/`) is retained for roster sync only. Win probabilities now come entirely from the causal ML ensemble (`src/intelligence/`, `src/ml/`).

**Key insight preserved:**  
The nibble-shift encoding for ODD player records, boundary record handling, and CRC logic were all validated during simulation development. That knowledge lives in `docs/vault/binary.md` and `src/binary/constants.py`.

---

## 2. Monte Carlo Batch Runner (`sim_logs/`, `batch_logs/`)

**Retired:** 2026-03-17  
**Files removed:**
- `data/sim_logs/` directory
- `data/batch_logs/` directory

**What it did:**  
Stored JSONL output from Monte Carlo simulation batches. Used as training signal for early ML models.

**Why it was retired:**  
With the headless runner gone, these directories have no writer. Real game data (`data/real/games_20XX.jsonl`) is the training source — synthetic sim data is no longer needed.

---

## 3. `pywinauto` / `pymem` Dependencies

**Retired:** 2026-03-17  
**Removed from:** `requirements.txt`

These were Windows-only dependencies for process automation and memory reading. Both are gone with the simulation layer. `requirements.txt` is now cross-platform.

---

## 4. Global pip freeze `requirements.txt`

**Retired:** 2026-03-17  
**Replaced with:** Audited minimal `requirements.txt` (280+ packages → ~45 packages)

The old file was a dumped global environment including `streamlit`, `roboflow`, `selenium`, `snowflake`, `twilio`, `yt-dlp`, `asyncua`, `onvif`, and dozens of other packages with zero connection to Epoch Engine. This created: slow installs, security surface, Docker bloat, and false signals about what the codebase actually depends on.
