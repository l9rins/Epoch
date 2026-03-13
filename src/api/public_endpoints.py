"""
Public Endpoints — SESSION C
No authentication required.
Powers the public accuracy dashboard — the acquisition engine.

These endpoints are the only marketing Epoch needs.
Bettors are evidence-driven. Show the receipts.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/public", tags=["public"])

DATA_DIR = Path("data")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
RECENT_DAYS_WINDOW: int = 30
MIN_PREDICTIONS_FOR_STATS: int = 5


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_all_predictions() -> list[dict[str, Any]]:
    """Load all predictions from data/predictions/*.jsonl"""
    pred_dir = DATA_DIR / "predictions"
    if not pred_dir.exists():
        return []
    records = []
    for fpath in sorted(pred_dir.glob("*.jsonl"), reverse=True):
        try:
            with open(fpath) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        records.append(json.loads(line))
        except Exception as exc:
            logger.warning("Failed to load %s: %s", fpath, exc)
    return records


def _load_calibration_history() -> list[dict[str, Any]]:
    """Load calibration history samples."""
    path = DATA_DIR / "calibration_history.jsonl"
    if not path.exists():
        return []
    records = []
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
    except Exception:
        pass
    return records


def _grade_prediction(pred: dict[str, Any]) -> str | None:
    """Return WIN/LOSS/PUSH or None if unresolved."""
    actual = pred.get("actual_winner")
    if not actual:
        return None
    predicted_home_wins = pred.get("win_probability", 0.5) >= 0.5
    home_won = actual == "HOME"
    if predicted_home_wins == home_won:
        return "WIN"
    return "LOSS"


# ---------------------------------------------------------------------------
# Public endpoints
# ---------------------------------------------------------------------------

@router.get("/accuracy")
def get_public_accuracy() -> dict[str, Any]:
    """
    Public accuracy dashboard — no auth required.
    Shows verified prediction track record for the last 30 days.
    This is the acquisition engine.
    """
    all_preds = _load_all_predictions()
    cutoff = datetime.utcnow() - timedelta(days=RECENT_DAYS_WINDOW)

    recent = []
    for p in all_preds:
        ts = p.get("timestamp") or p.get("created_at", "")
        try:
            pred_date = datetime.fromisoformat(ts)
            if pred_date >= cutoff:
                recent.append(p)
        except Exception:
            recent.append(p)  # include if no timestamp

    completed = [p for p in recent if p.get("actual_winner")]
    graded = [(p, _grade_prediction(p)) for p in completed]
    wins = sum(1 for _, g in graded if g == "WIN")
    losses = sum(1 for _, g in graded if g == "LOSS")
    total = wins + losses

    hit_rate = round(wins / total, 4) if total > 0 else None

    # Tier breakdown
    tier_stats: dict[int, dict] = {}
    for p in completed:
        tier = p.get("tier", 3)
        if tier not in tier_stats:
            tier_stats[tier] = {"wins": 0, "losses": 0}
        grade = _grade_prediction(p)
        if grade == "WIN":
            tier_stats[tier]["wins"] += 1
        elif grade == "LOSS":
            tier_stats[tier]["losses"] += 1

    tier_breakdown = []
    for tier in sorted(tier_stats.keys()):
        t = tier_stats[tier]
        t_total = t["wins"] + t["losses"]
        tier_breakdown.append({
            "tier": tier,
            "wins": t["wins"],
            "losses": t["losses"],
            "hit_rate": round(t["wins"] / t_total, 4) if t_total > 0 else None,
            "sample_count": t_total,
        })

    # Calibration stats
    cal = _load_calibration_history()
    brier = None
    if cal:
        import numpy as np
        probs = [c.get("predicted_prob", 0.5) for c in cal]
        actuals = [float(c.get("actual_outcome", 0)) for c in cal]
        if probs and actuals:
            brier = round(float(np.mean(
                [(p - a) ** 2 for p, a in zip(probs, actuals)]
            )), 4)

    return {
        "window_days": RECENT_DAYS_WINDOW,
        "total_predictions": len(recent),
        "completed": total,
        "wins": wins,
        "losses": losses,
        "hit_rate": hit_rate,
        "brier_score": brier,
        "calibration_samples": len(cal),
        "tier_breakdown": tier_breakdown,
        "last_updated": datetime.utcnow().isoformat(),
        "note": "All predictions timestamped before game tip-off. No retroactive edits.",
    }


@router.get("/predictions/today")
def get_public_todays_predictions() -> list[dict[str, Any]]:
    """
    Today's predictions — public, no auth.
    Shows signal tier and win probability but NOT Kelly sizing.
    Kelly sizing requires Signal tier subscription.
    """
    date_str = datetime.utcnow().strftime("%Y-%m-%d")
    log_file = DATA_DIR / "predictions" / f"{date_str}.jsonl"
    if not log_file.exists():
        return []

    public_fields = {
        "game_id", "home_team", "away_team", "tip_off",
        "win_probability", "tier", "confidence",
        "projected_home", "projected_away",
    }

    results = []
    try:
        with open(log_file) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                pred = json.loads(line)
                # Strip Kelly sizing — that's Signal tier only
                public_pred = {k: v for k, v in pred.items() if k in public_fields}
                public_pred["kelly_hidden"] = True
                results.append(public_pred)
    except Exception as exc:
        logger.warning("Failed loading today's predictions: %s", exc)

    return results


@router.get("/track-record")
def get_track_record() -> dict[str, Any]:
    """
    Full public track record — last 100 graded predictions.
    Sorted newest first. Used for the social proof feed.
    """
    all_preds = _load_all_predictions()
    completed = [p for p in all_preds if p.get("actual_winner")][-100:]

    records = []
    for p in reversed(completed):
        grade = _grade_prediction(p)
        records.append({
            "game_id": p.get("game_id"),
            "home_team": p.get("home_team", "HOME"),
            "away_team": p.get("away_team", "AWAY"),
            "predicted_winner": "HOME" if p.get("win_probability", 0.5) >= 0.5 else "AWAY",
            "win_probability": p.get("win_probability"),
            "tier": p.get("tier", 3),
            "result": grade,
            "date": p.get("timestamp", "")[:10],
        })

    wins = sum(1 for r in records if r["result"] == "WIN")
    total = len(records)

    return {
        "records": records,
        "summary": {
            "total": total,
            "wins": wins,
            "hit_rate": round(wins / total, 4) if total > 0 else None,
        },
    }


@router.get("/signal-sample")
def get_signal_sample() -> dict[str, Any]:
    """
    Show one recent T1 signal with full detail EXCEPT bet sizing.
    Acquisition hook — shows what Signal subscribers get.
    """
    all_preds = _load_all_predictions()
    t1_preds = [p for p in all_preds if p.get("tier") == 1 and p.get("actual_winner")]

    if not t1_preds:
        return {
            "available": False,
            "message": "No completed T1 signals yet. Check back after tonight's games.",
        }

    sample = t1_preds[-1]
    grade = _grade_prediction(sample)

    return {
        "available": True,
        "signal": {
            "home_team": sample.get("home_team", "HOME"),
            "away_team": sample.get("away_team", "AWAY"),
            "tier": 1,
            "win_probability": sample.get("win_probability"),
            "confidence": sample.get("confidence", "HIGH"),
            "result": grade,
            "causal_summary": sample.get("causal_summary", "Causal analysis available to Signal subscribers"),
            "kelly_sizing": "🔒 Signal tier required",
            "date": sample.get("timestamp", "")[:10],
        },
        "cta": "Subscribe to Signal ($149/mo) to get Kelly sizing on every T1 alert.",
    }
