import json
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from collections import defaultdict

SIGNAL_VALIDATION_PATH = Path("data/signal_validation_report.json")
TIER_PRECISION_TARGETS = {1: 0.650, 2: 0.580, 3: 0.540}
MIN_SIGNALS_TO_VALIDATE = 10

def load_resolved_journal_entries(
    journal_path: str = "data/betting_journal.jsonl",
) -> List[dict]:
    """Load only resolved journal entries (outcome is not None)."""
    path = Path(journal_path)
    if not path.exists():
        return []
    entries = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                if record.get("outcome") is not None:
                    entries.append(record)
            except Exception:
                continue
    return entries

def compute_expected_calibration_error(
    predicted_probs: List[float],
    outcomes: List[float],
    n_bins: int = 10,
) -> float:
    """
    Compute Expected Calibration Error (ECE).
    ECE measures how well predicted probabilities match actual frequencies.
    Lower is better. Target: < 0.10.
    """
    if len(predicted_probs) < n_bins:
        return float("nan")

    probs = np.array(predicted_probs)
    acts = np.array(outcomes)
    bin_edges = np.linspace(0, 1, n_bins + 1)
    ece = 0.0
    n = len(probs)

    for i in range(n_bins):
        mask = (probs >= bin_edges[i]) & (probs < bin_edges[i + 1])
        if mask.sum() == 0:
            continue
        bin_confidence = probs[mask].mean()
        bin_accuracy = acts[mask].mean()
        bin_weight = mask.sum() / n
        ece += bin_weight * abs(bin_confidence - bin_accuracy)

    return round(float(ece), 4)

def validate_signal_tiers(
    journal_entries: Optional[List[dict]] = None,
    game_logs: Optional[List[dict]] = None,
) -> dict:
    """
    Compute precision, recall, F1, and ECE per signal tier.
    Uses resolved betting journal entries as ground truth.
    Falls back to simulation if journal is empty.
    """
    if journal_entries is None:
        journal_entries = load_resolved_journal_entries()

    # Group by tier
    tier_results: Dict[int, dict] = {
        1: {"wins": 0, "losses": 0, "pushes": 0, "probs": [], "outcomes": []},
        2: {"wins": 0, "losses": 0, "pushes": 0, "probs": [], "outcomes": []},
        3: {"wins": 0, "losses": 0, "pushes": 0, "probs": [], "outcomes": []},
    }

    for entry in journal_entries:
        tier = entry.get("tier", 3)
        if tier not in tier_results:
            continue
        outcome = entry.get("outcome")
        prob = entry.get("epoch_win_probability", 0.5)
        tier_results[tier]["probs"].append(prob)

        if outcome == "WIN":
            tier_results[tier]["wins"] += 1
            tier_results[tier]["outcomes"].append(1.0)
        elif outcome == "LOSS":
            tier_results[tier]["losses"] += 1
            tier_results[tier]["outcomes"].append(0.0)
        elif outcome == "PUSH":
            tier_results[tier]["pushes"] += 1

    # Compute metrics per tier
    tier_metrics = {}
    all_targets_met = True

    for tier, stats in tier_results.items():
        total = stats["wins"] + stats["losses"] + stats["pushes"]
        if total < MIN_SIGNALS_TO_VALIDATE:
            tier_metrics[tier] = {
                "total_signals": total,
                "precision": None,
                "recall": None,
                "f1": None,
                "ece": None,
                "hit_rate": None,
                "status": "INSUFFICIENT_DATA",
                "target": TIER_PRECISION_TARGETS[tier],
                "target_met": None,
            }
            continue

        relevant = stats["wins"] + stats["losses"]
        precision = stats["wins"] / relevant if relevant > 0 else 0.0
        # Recall approximation: what fraction of wins we caught
        # (requires knowing total predictable wins — use win rate as proxy)
        expected_wins = total * 0.54  # home win rate prior
        recall = stats["wins"] / max(expected_wins, 1.0)
        recall = min(1.0, recall)
        f1 = (
            2 * precision * recall / (precision + recall)
            if (precision + recall) > 0 else 0.0
        )
        ece = compute_expected_calibration_error(
            stats["probs"], stats["outcomes"]
        ) if len(stats["outcomes"]) >= 10 else float("nan")

        target = TIER_PRECISION_TARGETS[tier]
        target_met = precision >= target
        if not target_met:
            all_targets_met = False

        tier_metrics[tier] = {
            "total_signals": total,
            "wins": stats["wins"],
            "losses": stats["losses"],
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "ece": ece,
            "hit_rate": round(stats["wins"] / total, 4),
            "status": "TARGET_MET" if target_met else "BELOW_TARGET",
            "target": target,
            "target_met": target_met,
        }

    # Signal type breakdown
    signal_type_stats: Dict[str, dict] = defaultdict(
        lambda: {"wins": 0, "total": 0}
    )
    for entry in journal_entries:
        st = entry.get("signal_type", "UNKNOWN")
        signal_type_stats[st]["total"] += 1
        if entry.get("outcome") == "WIN":
            signal_type_stats[st]["wins"] += 1

    signal_type_precision = {
        st: round(stats["wins"] / max(stats["total"], 1), 4)
        for st, stats in signal_type_stats.items()
        if stats["total"] >= 5
    }

    # Overall stats
    all_wins = sum(s["wins"] for s in tier_results.values())
    all_total = sum(
        s["wins"] + s["losses"] + s["pushes"]
        for s in tier_results.values()
    )

    report = {
        "total_resolved_signals": all_total,
        "overall_precision": round(all_wins / max(all_total, 1), 4),
        "tier_metrics": tier_metrics,
        "signal_type_precision": signal_type_precision,
        "all_targets_met": all_targets_met,
        "ece_target": 0.10,
        "data_source": "betting_journal" if journal_entries else "none",
        "note": (
            "Insufficient journal data — populate betting journal "
            "with 10+ resolved bets per tier for meaningful validation"
            if all_total < 30 else "Validation complete"
        ),
    }

    SIGNAL_VALIDATION_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(SIGNAL_VALIDATION_PATH, "w") as f:
        json.dump(report, f, indent=2)

    return report

def get_dynamic_tier_thresholds(
    validation_report: dict,
) -> Dict[int, dict]:
    """
    Compute dynamic tier thresholds based on validation results.
    If Tier 1 precision is below target, tighten the threshold.
    If Tier 1 precision exceeds target, allow slight relaxation.
    """
    BASE_THRESHOLDS = {
        1: {"min_model_agreement": 8, "min_wp": 0.70, "cooldown_s": 60},
        2: {"min_model_agreement": 5, "min_wp": 0.62, "cooldown_s": 90},
        3: {"min_model_agreement": 3, "min_wp": 0.55, "cooldown_s": 120},
    }
    adjusted = {}
    tier_metrics = validation_report.get("tier_metrics", {})

    for tier, base in BASE_THRESHOLDS.items():
        metrics = tier_metrics.get(tier, {})
        precision = metrics.get("precision")
        target = TIER_PRECISION_TARGETS[tier]
        threshold = base.copy()

        if precision is not None:
            if precision < target - 0.05:
                # Tighten: require higher win probability
                threshold["min_wp"] = min(0.85, base["min_wp"] + 0.05)
                threshold["min_model_agreement"] = min(12, base["min_model_agreement"] + 1)
                threshold["cooldown_s"] = base["cooldown_s"] + 30
                threshold["adjustment"] = "TIGHTENED"
            elif precision > target + 0.05:
                # Relax: can afford lower threshold
                threshold["min_wp"] = max(0.55, base["min_wp"] - 0.02)
                threshold["adjustment"] = "RELAXED"
            else:
                threshold["adjustment"] = "NO_CHANGE"
        else:
            threshold["adjustment"] = "NO_DATA"

        adjusted[tier] = threshold

    return adjusted
