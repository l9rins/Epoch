from dataclasses import dataclass, field
from typing import List, Optional
import time
from datetime import datetime
from pathlib import Path
import json


@dataclass
class SignalAlert:
    timestamp: float
    alert_type: str  # "WIN_PROB_THRESHOLD" | "MOMENTUM_SHIFT" | "PROJECTION_UPDATE"
    tier: int  # 1 = critical, 2 = notable, 3 = informational
    value: float
    message: str


class AlertEngine:
    # Cooldown periods (in game-time seconds) per alert type
    COOLDOWNS = {
        "WIN_PROB_THRESHOLD": 60.0,
        "MOMENTUM_SHIFT": 90.0,
        "PROJECTION_UPDATE": 120.0,
    }

    # Win probability thresholds and their tiers
    WIN_PROB_BOUNDARIES = [
        (0.90, 1),  # 90% → Tier 1 (critical)
        (0.75, 2),  # 75% → Tier 2 (notable)
        (0.60, 3),  # 60% → Tier 3 (informational)
    ]

    def __init__(self, log_dir: Optional[str] = None):
        self.last_win_prob_interval = None
        self.momentum_history: List[tuple] = []
        self.last_projection_time = None
        self.last_projected_score = None
        self.last_alert_times: dict = {}  # alert_type → last game_time fired

        # Logging (disabled when log_dir is None, e.g. in tests)
        self.log_file = None
        if log_dir is not None:
            log_path = Path(log_dir) / f"{datetime.now().strftime('%Y-%m-%d')}.jsonl"
            log_path.parent.mkdir(parents=True, exist_ok=True)
            self.log_file = log_path

    def _log_alert(self, alert: SignalAlert):
        if self.log_file is None:
            return
        with open(self.log_file, "a") as f:
            f.write(json.dumps({
                "timestamp": alert.timestamp,
                "alert_type": alert.alert_type,
                "tier": alert.tier,
                "value": alert.value,
                "message": alert.message,
            }) + "\n")

    def _on_cooldown(self, alert_type: str, game_time: float) -> bool:
        """Check if an alert type is still within its cooldown period."""
        last_time = self.last_alert_times.get(alert_type)
        if last_time is None:
            return False
        return (game_time - last_time) < self.COOLDOWNS.get(alert_type, 0)

    def _record_fire(self, alert_type: str, game_time: float):
        self.last_alert_times[alert_type] = game_time

    def process(
        self,
        game_time: float,
        win_prob: float,
        momentum: float,
        proj_home: int,
        proj_away: int,
        is_stale: bool = False,
    ) -> List[SignalAlert]:
        alerts = []
        now = time.time()

        # --- Win Prob Threshold Alerts ---
        alerts.extend(self._check_win_prob(now, game_time, win_prob))

        # --- Momentum Shift Alerts ---
        alerts.extend(self._check_momentum(now, game_time, momentum))

        # --- Projection Update Alerts ---
        alerts.extend(self._check_projection(now, game_time, proj_home, proj_away))

        for a in alerts:
            if is_stale:
                # Session A: Pipeline Armor — downgrade tier by 1 (T1->T2, T2->T3, T3->T3)
                a.tier = min(3, a.tier + 1)
                a.message = f"[STALE] {a.message}"
            self._log_alert(a)

        return alerts

    def _check_win_prob(self, now: float, game_time: float, win_prob: float) -> List[SignalAlert]:
        """Fire when win probability crosses a meaningful threshold."""
        alerts = []

        # Determine which interval the current win_prob falls in
        intervals = [0.0, 0.1, 0.25, 0.4, 0.6, 0.75, 0.9, 1.0]
        curr_interval = sum(1 for t in intervals if win_prob >= t) - 1

        if self.last_win_prob_interval is not None and curr_interval != self.last_win_prob_interval:
            if not self._on_cooldown("WIN_PROB_THRESHOLD", game_time):
                # Find which boundary was crossed and its tier
                crossed_idx = max(curr_interval, self.last_win_prob_interval)
                boundary = intervals[crossed_idx]
                boundary_pct = max(boundary, 1.0 - boundary) * 100

                # Only fire for significant thresholds (≥60%)
                if boundary_pct >= 60:
                    tier = 3  # default informational
                    for threshold_pct, threshold_tier in self.WIN_PROB_BOUNDARIES:
                        if boundary >= threshold_pct:
                            tier = threshold_tier
                            break

                    team_str = "HOME" if win_prob >= 0.5 else "AWAY"
                    direction = "↑" if curr_interval > self.last_win_prob_interval else "↓"

                    alerts.append(SignalAlert(
                        timestamp=now,
                        alert_type="WIN_PROB_THRESHOLD",
                        tier=tier,
                        value=win_prob,
                        message=f"{direction} Win probability crossed {boundary_pct:g}% for {team_str}",
                    ))
                    self._record_fire("WIN_PROB_THRESHOLD", game_time)

        self.last_win_prob_interval = curr_interval
        return alerts

    def _check_momentum(self, now: float, game_time: float, momentum: float) -> List[SignalAlert]:
        """Fire when momentum swings >30 points within a 60-second window."""
        alerts = []

        # Prune stale history (older than 60 game-time seconds)
        self.momentum_history = [
            (t, m) for t, m in self.momentum_history if game_time - t <= 60
        ]
        self.momentum_history.append((game_time, momentum))

        if len(self.momentum_history) < 2:
            return alerts

        min_m = min(m for _, m in self.momentum_history)
        max_m = max(m for _, m in self.momentum_history)
        swing = max_m - min_m

        if swing > 30 and not self._on_cooldown("MOMENTUM_SHIFT", game_time):
            # Determine swing tier by magnitude
            if swing > 60:
                tier = 1
            elif swing > 45:
                tier = 2
            else:
                tier = 3

            direction = "→ HOME" if momentum > 0 else "→ AWAY" if momentum < 0 else "NEUTRAL"
            alerts.append(SignalAlert(
                timestamp=now,
                alert_type="MOMENTUM_SHIFT",
                tier=tier,
                value=momentum,
                message=f"Momentum swing of {swing:.0f} in <60s {direction} (now {momentum:+.1f})",
            ))
            self._record_fire("MOMENTUM_SHIFT", game_time)
            # Reset window after firing to prevent re-triggering on same swing
            self.momentum_history.clear()
            self.momentum_history.append((game_time, momentum))

        return alerts

    def _check_projection(
        self, now: float, game_time: float, proj_home: int, proj_away: int,
    ) -> List[SignalAlert]:
        """Fire when projected score changes meaningfully, at most every 2 minutes."""
        alerts = []

        if self.last_projection_time is not None and (game_time - self.last_projection_time) < 120:
            return alerts

        # Only fire if projection actually changed (or first time)
        current_proj = (proj_home, proj_away)
        if self.last_projected_score is not None and current_proj == self.last_projected_score:
            return alerts

        alerts.append(SignalAlert(
            timestamp=now,
            alert_type="PROJECTION_UPDATE",
            tier=3,
            value=game_time,
            message=f"Projected final: {proj_home}-{proj_away}",
        ))
        self.last_projection_time = game_time
        self.last_projected_score = current_proj
        return alerts
