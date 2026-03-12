from dataclasses import dataclass

@dataclass
class ValueBet:
    has_edge: bool
    edge: float
    kelly_fraction: float
    recommendation: str
    confidence: float

class ValueDetector:
    def __init__(self, confidence_buffer: float = 0.05):
        # We need an edge of at least 5% purely to cover vig/juice
        self.buffer = confidence_buffer

    def detect(self, our_win_prob: float, live_odds: int) -> ValueBet:
        # Convert moneyline odds to implied probability
        if live_odds < 0:
            implied_prob = 100 / (abs(live_odds) + 100)
        else:
            implied_prob = live_odds / (live_odds + 100)
            
        edge = our_win_prob - implied_prob
        
        # Kelly criterion fraction = Edge / Odds (in decimal relative to 1:1)
        # Simplified Kelly: edge / (1 - implied_prob)
        kelly_fraction = 0.0
        if implied_prob < 1.0 and edge > 0:
            kelly_fraction = edge / (1 - implied_prob)
            
        has_edge = edge > self.buffer
        
        if edge > 0.15:
            rec = "STRONG VALUE"
            conf = 0.9
        elif edge > 0.08:
            rec = "VALUE BET"
            conf = 0.75
        elif edge > self.buffer:
            rec = "MARGINAL"
            conf = 0.6
        elif edge > -self.buffer:
            rec = "NO EDGE"
            conf = 0.5
        else:
            rec = "FADE"
            conf = 0.8 # high confidence to fade
            
        return ValueBet(has_edge, edge, min(1.0, max(0.0, kelly_fraction)), rec, conf)

if __name__ == "__main__":
    detector = ValueDetector()
    res = detector.detect(our_win_prob=0.65, live_odds=-110) # Implied = 52.4%
    print(f"Sample Value Check: {res}")
