from dataclasses import dataclass

class FatigueModel:
    """
    Models player and team fatigue effects on performance.
    Adjusts win probabilities based on game progression (quarter) 
    and schedule density (back-to-back games).
    """
    
    # Q4 performance multiplier based on minutes played
    QUARTER_FATIGUE = {1: 1.00, 2: 0.97, 3: 0.94, 4: 0.90}
    BACK_TO_BACK_PENALTY = 0.05  # 5% performance reduction
    
    def get_fatigue_factor(self, quarter: int, is_back_to_back: bool) -> float:
        """Calculate the fatigue multiplier for a given situation."""
        base = self.QUARTER_FATIGUE.get(quarter, 0.90)
        if is_back_to_back:
            base -= self.BACK_TO_BACK_PENALTY
        return round(base, 2)
    
    def adjust_win_probability(self, win_prob: float, 
                               home_fatigue: float, 
                               away_fatigue: float) -> float:
        """
        Adjust base win probability based on the relative fatigue of both teams.
        fatigue_factor of 1.0 is fresh, lower is more tired.
        """
        # fatigue_diff > 0 means home is fresher than away
        # fatigue_diff < 0 means away is fresher than home
        fatigue_diff = home_fatigue - away_fatigue
        
        # Simple linear adjustment: 10% swing per 1.0 difference in fatigue factor
        adjustment = fatigue_diff * 0.1
        
        adjusted_prob = win_prob + adjustment
        return max(0.05, min(0.95, round(adjusted_prob, 3)))
