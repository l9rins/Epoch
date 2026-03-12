import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict

JOURNAL_PATH = Path("data/betting_journal.jsonl")
EDGE_PROFILES_PATH = Path("data/edge_profiles.json")

# Minimum samples before personalizing edge profile
MIN_SAMPLES_FOR_EDGE_PROFILE = 30

@dataclass
class JournalEntry:
    journal_id: str
    user_id: str
    timestamp: str
    game_id: str
    signal_type: str
    tier: int
    direction: str
    epoch_win_probability: float
    decimal_odds: float
    recommended_bet_size: float
    actual_bet_size: float
    bankroll_at_time: float
    recommended_fraction: float
    causal_context: Optional[str]
    outcome: Optional[str]
    profit_loss: Optional[float]
    resolved_at: Optional[str]
    tags: List[str]

def create_journal_entry(
    user_id: str,
    game_id: str,
    signal_type: str,
    tier: int,
    direction: str,
    epoch_win_probability: float,
    decimal_odds: float,
    recommended_bet_size: float,
    actual_bet_size: float,
    bankroll_at_time: float,
    recommended_fraction: float,
    causal_context: Optional[str] = None,
    tags: Optional[List[str]] = None,
) -> JournalEntry:
    return JournalEntry(
        journal_id=str(uuid.uuid4()),
        user_id=user_id,
        timestamp=datetime.utcnow().isoformat(),
        game_id=game_id,
        signal_type=signal_type,
        tier=tier,
        direction=direction,
        epoch_win_probability=epoch_win_probability,
        decimal_odds=decimal_odds,
        recommended_bet_size=recommended_bet_size,
        actual_bet_size=actual_bet_size,
        bankroll_at_time=bankroll_at_time,
        recommended_fraction=recommended_fraction,
        causal_context=causal_context,
        outcome=None,
        profit_loss=None,
        resolved_at=None,
        tags=tags or [],
    )

def append_journal_entry(entry: JournalEntry) -> None:
    JOURNAL_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(JOURNAL_PATH, "a") as f:
        f.write(json.dumps(asdict(entry)) + "\n")

def resolve_outcome(
    journal_id: str,
    outcome: str,
    profit_loss: float,
) -> bool:
    """
    Resolve a journal entry with WIN/LOSS/PUSH outcome.
    Rewrites the JSONL file with updated entry.
    Returns True if entry found and updated.
    """
    if not JOURNAL_PATH.exists():
        return False
    lines = []
    found = False
    resolved_at = datetime.utcnow().isoformat()
    with open(JOURNAL_PATH) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            if record.get("journal_id") == journal_id:
                record["outcome"] = outcome
                record["profit_loss"] = profit_loss
                record["resolved_at"] = resolved_at
                found = True
            lines.append(json.dumps(record))
    if found:
        with open(JOURNAL_PATH, "w") as f:
            f.write("\n".join(lines) + "\n")
    return found

def load_user_journal(user_id: str) -> List[dict]:
    """Load all journal entries for a specific user."""
    if not JOURNAL_PATH.exists():
        return []
    entries = []
    with open(JOURNAL_PATH) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                if record.get("user_id") == user_id:
                    entries.append(record)
            except Exception:
                continue
    return entries

def compute_edge_profile(user_id: str) -> dict:
    """
    Compute personalized edge profile for a user from their journal history.
    Returns per-signal-type ROI, hit rates, and Kelly multiplier recommendations.
    """
    entries = [e for e in load_user_journal(user_id) if e.get("outcome") is not None]

    if not entries:
        return {
            "user_id": user_id,
            "total_bets": 0,
            "overall_roi": 0.0,
            "signal_type_edges": {},
            "best_spots": [],
            "worst_spots": [],
            "kelly_multipliers": {},
            "profile_confidence": "NO_DATA",
        }

    # Per signal type breakdown
    signal_stats: Dict[str, dict] = {}
    for entry in entries:
        st = entry.get("signal_type", "UNKNOWN")
        if st not in signal_stats:
            signal_stats[st] = {
                "wins": 0, "losses": 0, "pushes": 0,
                "total_wagered": 0.0, "total_profit": 0.0,
                "implied_probs": [],
            }
        outcome = entry.get("outcome")
        bet_size = entry.get("actual_bet_size", 0.0)
        pl = entry.get("profit_loss", 0.0) or 0.0
        signal_stats[st]["total_wagered"] += bet_size
        signal_stats[st]["total_profit"] += pl
        signal_stats[st]["implied_probs"].append(
            1.0 / entry.get("decimal_odds", 1.909)
        )
        if outcome == "WIN":
            signal_stats[st]["wins"] += 1
        elif outcome == "LOSS":
            signal_stats[st]["losses"] += 1
        elif outcome == "PUSH":
            signal_stats[st]["pushes"] += 1

    signal_type_edges = {}
    kelly_multipliers = {}
    for st, stats in signal_stats.items():
        total = stats["wins"] + stats["losses"] + stats["pushes"]
        if total == 0:
            continue
        hit_rate = stats["wins"] / max(stats["wins"] + stats["losses"], 1)
        roi = stats["total_profit"] / max(stats["total_wagered"], 1.0)
        avg_implied = (
            sum(stats["implied_probs"]) / len(stats["implied_probs"])
            if stats["implied_probs"] else 0.524
        )
        personal_edge = hit_rate - avg_implied
        signal_type_edges[st] = {
            "hit_rate": round(hit_rate, 4),
            "roi": round(roi, 4),
            "personal_edge": round(personal_edge, 4),
            "sample_count": total,
            "total_profit": round(stats["total_profit"], 2),
        }
        # Kelly multiplier: if you beat Epoch's prior on this signal type,
        # increase sizing. If you underperform, reduce it.
        if total >= MIN_SAMPLES_FOR_EDGE_PROFILE:
            if personal_edge > 0.05:
                kelly_multipliers[st] = 1.25  # you have alpha here → size up
            elif personal_edge > 0.02:
                kelly_multipliers[st] = 1.10
            elif personal_edge < -0.02:
                kelly_multipliers[st] = 0.75  # you're losing on this type → size down
            else:
                kelly_multipliers[st] = 1.00

    # Overall ROI
    total_wagered = sum(e.get("actual_bet_size", 0) for e in entries)
    total_profit = sum(e.get("profit_loss", 0) or 0 for e in entries)
    overall_roi = total_profit / max(total_wagered, 1.0)

    # Best and worst spots
    sorted_edges = sorted(
        signal_type_edges.items(),
        key=lambda x: x[1]["roi"],
        reverse=True,
    )
    best_spots = [
        {"signal_type": k, "roi": v["roi"], "sample_count": v["sample_count"]}
        for k, v in sorted_edges[:3]
        if v["roi"] > 0
    ]
    worst_spots = [
        {"signal_type": k, "roi": v["roi"], "sample_count": v["sample_count"]}
        for k, v in sorted_edges[-3:]
        if v["roi"] < 0
    ]

    total_bets = len(entries)
    profile_confidence = (
        "HIGH" if total_bets >= 100
        else "MEDIUM" if total_bets >= MIN_SAMPLES_FOR_EDGE_PROFILE
        else "LOW"
    )

    profile = {
        "user_id": user_id,
        "total_bets": total_bets,
        "overall_roi": round(overall_roi, 4),
        "signal_type_edges": signal_type_edges,
        "best_spots": best_spots,
        "worst_spots": worst_spots,
        "kelly_multipliers": kelly_multipliers,
        "profile_confidence": profile_confidence,
        "computed_at": datetime.utcnow().isoformat(),
    }

    # Persist edge profile
    EDGE_PROFILES_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        existing = {}
        if EDGE_PROFILES_PATH.exists():
            with open(EDGE_PROFILES_PATH) as f:
                existing = json.load(f)
        existing[user_id] = profile
        with open(EDGE_PROFILES_PATH, "w") as f:
            json.dump(existing, f, indent=2)
    except Exception as e:
        print(f"Warning persisting edge profile: {e}")

    return profile
