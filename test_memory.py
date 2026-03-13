import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.simulation.process_manager import get_nba2k14_pid
from src.simulation.memory_reader import MemoryReader

pid = get_nba2k14_pid()
if not pid:
    print("NBA 2K14 process not found.")
    sys.exit(1)

print(f"Connecting to PID: {pid}")
reader = MemoryReader(pid)
state = reader.read_state()

if state:
    print("Memory read SUCCESS!")
    print(f"Quarter: {state.quarter}")
    print(f"Clock: {state.clock}")
    print(f"Score: {state.home_score} - {state.away_score}")
else:
    print("Memory read FAILED or returned None.")
