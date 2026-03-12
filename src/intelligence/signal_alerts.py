from dataclasses import dataclass
from typing import List
import time
from datetime import datetime
from pathlib import Path
import json

@dataclass
class SignalAlert:
    timestamp: float
    alert_type: str  # "WIN_PROB_THRESHOLD" | "MOMENTUM_SHIFT" | "PROJECTION_UPDATE"
    value: float
    message: str

class AlertEngine:
    def __init__(self):
        self.last_win_prob_threshold = None
        self.momentum_history = []  # List of (game_time, momentum)
        self.last_projection_time = None
        self.log_file = Path("data") / "signal_alerts" / f"{datetime.now().strftime('%Y-%m-%d')}.jsonl"
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        
    def _log_alert(self, alert: SignalAlert):
        with open(self.log_file, "a") as f:
            f.write(json.dumps({
                "timestamp": alert.timestamp,
                "alert_type": alert.alert_type,
                "value": alert.value,
                "message": alert.message
            }) + "\n")

    def process(self, game_time: float, win_prob: float, momentum: float, proj_home: int, proj_away: int) -> List[SignalAlert]:
        alerts = []
        now = time.time()
        
        # Win Prob thresholds (both directions)
        intervals = [0.0, 0.1, 0.25, 0.4, 0.6, 0.75, 0.9, 1.0]
        curr_interval = sum(1 for t in intervals if win_prob >= t) - 1
        
        if self.last_win_prob_threshold is not None and curr_interval != self.last_win_prob_threshold:
            higher = max(curr_interval, self.last_win_prob_threshold)
            boundary = intervals[higher]
            team_str = "HOME" if win_prob >= 0.5 else "AWAY"
            boundary_pct = max(boundary, 1.0 - boundary) * 100
            if boundary_pct >= 60:
                alerts.append(SignalAlert(
                    timestamp=now,
                    alert_type="WIN_PROB_THRESHOLD",
                    value=win_prob,
                    message=f"Win probability crossed {boundary_pct:g}% threshold for {team_str}"
                ))
        self.last_win_prob_threshold = curr_interval
        
        # Momentum shift (>30 in under 60 seconds)
        # Clean old history > 60 seconds
        self.momentum_history = [(t, m) for t, m in self.momentum_history if game_time - t <= 60]
        self.momentum_history.append((game_time, momentum))
        
        if self.momentum_history:
            min_m = min(m for t, m in self.momentum_history)
            max_m = max(m for t, m in self.momentum_history)
            
            if max_m - min_m > 30 and abs(momentum - self.momentum_history[-1][1]) < 0.1: # Only fire near the edges? No just check if current triggers it
                # To prevent spamming, verify the current momentum IS the max or min causing the >30 shift
                if momentum == max_m or momentum == min_m:
                    # Let's check when the last MOMENTUM_SHIFT was logged to avoid spamming
                    # We can clear history after firing an alert
                    alerts.append(SignalAlert(
                        timestamp=now,
                        alert_type="MOMENTUM_SHIFT",
                        value=momentum,
                        message=f"Momentum shifted by >30 in under 60s (now {momentum:+.1f})"
                    ))
                    self.momentum_history.clear()
                    self.momentum_history.append((game_time, momentum))
                
        # Projection Update (every 2 minutes of game time = 120 seconds)
        if self.last_projection_time is None or game_time - self.last_projection_time >= 120:
            alerts.append(SignalAlert(
                timestamp=now,
                alert_type="PROJECTION_UPDATE",
                value=game_time,
                message=f"Projected final score updated: {proj_home}-{proj_away}"
            ))
            self.last_projection_time = game_time
            
        for a in alerts:
            self._log_alert(a)
            
        return alerts
