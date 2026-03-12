class SpreadCalculator:
    def __init__(self, pregame_spread=-4.5):
        # Default home favored by 4.5
        self.pregame_spread = pregame_spread
        
    def calculate(self, state, momentum, projected_total) -> float:
        score_diff = state["home_score"] - state["away_score"]
        base_spread = -(score_diff)
        
        time_rem = state["time_remaining"]
        time_weight = time_rem / 2880.0
        
        momentum_adj = momentum * 0.05
        pace_adj = (projected_total - 220) * 0.02
        
        # In a faster pace game, a lead is slightly less "safe", so adjust the spread
        # Here pace_adj scales the impact of momentum minimally
        
        live_spread = (base_spread * (1 - time_weight)) + (self.pregame_spread * time_weight) + momentum_adj + pace_adj
        
        # Round to nearest 0.5
        return round(live_spread * 2) / 2

if __name__ == "__main__":
    calc = SpreadCalculator(pregame_spread=-5.5)
    sample_state = {"home_score": 100, "away_score": 90, "time_remaining": 600} # Q4, Home +10
    print(f"Live Spread: {calc.calculate(sample_state, momentum=10, projected_total=230)}")
