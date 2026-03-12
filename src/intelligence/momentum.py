import math
from collections import deque
from src.simulation.memory_reader import GameState

class MomentumTracker:
    def __init__(self):
        self.history = deque() # Store (game_time, home_score, away_score)
        
    def _game_time(self, state: GameState) -> float:
        q = state.quarter if state.quarter <= 4 else 4
        time_remaining = max(0, ((4 - q) * 720) + state.clock)
        return (4 * 720) - time_remaining

    def update(self, state: GameState) -> float:
        current_time = self._game_time(state)
        
        # Maintain rolling window of last 3 minutes (180 seconds)
        # Note: if the game time jumps backwards (like a reset), clear history
        if self.history and current_time < self.history[-1][0]:
            self.history.clear()
            
        self.history.append((current_time, state.home_score, state.away_score))
        
        while self.history and current_time - self.history[0][0] > 180:
            self.history.popleft()
            
        momentum = 0.0
        
        # Process scoring events
        for i in range(1, len(self.history)):
            prev_time, prev_home, prev_away = self.history[i-1]
            curr_time, curr_home, curr_away = self.history[i]
            
            home_pts = curr_home - prev_home
            away_pts = curr_away - prev_away
            
            if home_pts > 0:
                event_age = current_time - curr_time
                momentum += (home_pts * 10) * (0.9 ** event_age)
                
            if away_pts > 0:
                event_age = current_time - curr_time
                momentum -= (away_pts * 10) * (0.9 ** event_age)
                
        # Clamp between -100 and 100
        return max(-100.0, min(100.0, momentum))

    def __call__(self, state: GameState) -> float:
        return self.update(state)
