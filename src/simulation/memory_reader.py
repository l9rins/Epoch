import time
from dataclasses import dataclass
from typing import Optional

try:
    import pymem
    import pymem.exception
except ImportError:
    pymem = None

@dataclass
class GameState:
    timestamp: float
    quarter: int
    clock: float
    home_score: int
    away_score: int
    possession: int

GAME_ADDRESSES = {
    'home_score':  0x01DE2188,
    'away_score':  0x01DE260C,
    'quarter':     0x01DEE5EC,
    'clock':       0x01DEE638,
    'possession':  0x01CE76FC,
}

class MemoryReader:
    def __init__(self, pid: int):
        if pymem is None:
            raise ImportError("pymem is not installed")
        self.pm = pymem.Pymem()
        self.pm.open_process_from_id(pid)
    
    def read_state(self) -> Optional[GameState]:
        try:
            # Phase 5: Placeholders - currently we are not really attached
            # but if we were attached to a real game, this would read memory.
            # Using read_int and read_float as placeholders.
            # For phase 5, we will always return a default state unless memory reading actually works
            
            # Since PLACEHOLDER_ADDRESSES are not valid memory pointers, reading them would throw an exception
            # We wrap in a try-except to return a dummy state for testing the pipeline if it fails to read
            try:
                q = self.pm.read_int(GAME_ADDRESSES['quarter'])
                clk = self.pm.read_float(GAME_ADDRESSES['clock'])
                hs = self.pm.read_int(GAME_ADDRESSES['home_score'])
                as_ = self.pm.read_int(GAME_ADDRESSES['away_score'])
                pos = self.pm.read_int(GAME_ADDRESSES['possession'])
                return GameState(time.time(), q, clk, hs, as_, pos)
            except pymem.exception.MemoryReadError:
                # Return dummy state for phase 5 until offsets are found
                return GameState(time.time(), 1, 720.0, 0, 0, 0)
                
        except pymem.exception.ProcessNotFound:
            return None
        except Exception:
            return None
