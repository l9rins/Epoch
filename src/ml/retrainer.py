import json
import time
from datetime import datetime, date
from pathlib import Path
from typing import Optional

RETRAINING_REPORT_PATH = Path("data/retraining_report.json")
DATA_FRESHNESS_HOURS = 24

def _is_data_fresh() -> bool:
    """Check if real game logs were pulled within freshness window."""
    from src.ml.real_data_pipeline import GAME_LOGS_PATH
    if not GAME_LOGS_PATH.exists():
        return False
    mtime = GAME_LOGS_PATH.stat().st_mtime
    age_hours = (time.time() - mtime) / 3600
    return age_hours < DATA_FRESHNESS_HOURS

def run_full_retraining(
    force_data_refresh: bool = False,
    seasons: Optional[list] = None,
) -> dict:
    """
    Run full retraining pipeline across all 4 intelligence systems.
    Returns comprehensive report of improvements.
    """
    start_time = time.time()
    report = {
        "started_at": datetime.utcnow().isoformat(),
        "steps": {},
        "improvements": {},
        "errors": [],
    }

    print("=" * 60)
    print("EPOCH ENGINE — FULL RETRAINING PIPELINE")
    print("=" * 60)

    # Step 1: Pull real data
    print("\nStep 1: Real Data Pipeline")
    try:
        from src.ml.real_data_pipeline import (
            run_real_data_pipeline, load_game_logs,
            load_player_logs, load_injury_logs,
        )
        if force_data_refresh or not _is_data_fresh():
            data_result = run_real_data_pipeline(seasons=seasons)
        else:
            print("  Data is fresh — skipping API pull")
            data_result = {"status": "cached"}

        game_logs = load_game_logs()
        player_logs = load_player_logs()
        injury_logs = load_injury_logs()

        report["steps"]["data_pipeline"] = {
            "status": "OK",
            "total_games": len(game_logs),
            "total_player_logs": len(player_logs),
            "injury_proxy_games": len(injury_logs),
        }
        print(f"  Games: {len(game_logs)}, Players: {len(player_logs)}, Injury: {len(injury_logs)}")
    except Exception as e:
        report["errors"].append(f"Data pipeline: {e}")
        report["steps"]["data_pipeline"] = {"status": "ERROR", "error": str(e)}
        print(f"  ERROR: {e}")
        game_logs, player_logs, injury_logs = [], [], []

    # Step 2: Feature engineering + ensemble retraining
    print("\nStep 2: Feature Engineering + Ensemble Retraining")
    try:
        from src.ml.feature_engineer import build_feature_matrix
        from src.ml.ensemble_model import train_ensemble, load_ensemble_meta

        if len(game_logs) >= 200:
            X, y = build_feature_matrix(game_logs)
            ensemble_result = train_ensemble(X, y)
            report["steps"]["ensemble"] = {
                "status": "RETRAINED",
                "ensemble_auc": ensemble_result["ensemble_auc"],
                "ensemble_brier": ensemble_result["ensemble_brier"],
                "auc_target_met": ensemble_result["auc_target_met"],
                "brier_target_met": ensemble_result["brier_target_met"],
            }
            report["improvements"]["auc"] = {
                "before": 0.837,
                "after": ensemble_result["ensemble_auc"],
                "delta": round(ensemble_result["ensemble_auc"] - 0.837, 4),
            }
            report["improvements"]["brier"] = {
                "before": 0.2146,
                "after": ensemble_result["ensemble_brier"],
                "delta": round(ensemble_result["ensemble_brier"] - 0.2146, 4),
            }
            print(f"  AUC: 0.837 -> {ensemble_result['ensemble_auc']}")
            print(f"  Brier: 0.2146 -> {ensemble_result['ensemble_brier']}")
        else:
            print(f"  Only {len(game_logs)} games — need 200+ for retraining")
            report["steps"]["ensemble"] = {"status": "SKIPPED", "reason": "insufficient_data"}
    except Exception as e:
        report["errors"].append(f"Ensemble: {e}")
        report["steps"]["ensemble"] = {"status": "ERROR", "error": str(e)}
        print(f"  ERROR: {e}")

    # Step 3: Causal weight learning
    print("\nStep 3: Causal Weight Learning")
    try:
        from src.intelligence.causal_learner import learn_all_causal_weights
        causal_result = learn_all_causal_weights(injury_logs, game_logs)
        report["steps"]["causal_learning"] = {
            "status": "OK",
            "learned_edges": len(causal_result["learned_edges"]),
            "avg_r2": causal_result["avg_r2"],
            "r2_target_met": causal_result["r2_target_met"],
        }
        report["improvements"]["causal_r2"] = {
            "before": 0.0,
            "after": causal_result["avg_r2"],
            "delta": causal_result["avg_r2"],
        }
        print(f"  Learned edges: {len(causal_result['learned_edges'])}")
        print(f"  Average R²: {causal_result['avg_r2']}")
    except Exception as e:
        report["errors"].append(f"Causal learning: {e}")
        report["steps"]["causal_learning"] = {"status": "ERROR", "error": str(e)}
        print(f"  ERROR: {e}")

    # Step 4: Player distributions
    print("\nStep 4: Per-Player Distribution Learning")
    try:
        from src.simulation.player_distributions import learn_all_player_distributions
        distributions = learn_all_player_distributions(player_logs)
        real_count = sum(1 for d in distributions.values() if d.data_source == "real")
        report["steps"]["player_distributions"] = {
            "status": "OK",
            "total_players": len(distributions),
            "real_distributions": real_count,
            "archetype_fallbacks": len(distributions) - real_count,
        }
        print(f"  Real distributions: {real_count}/{len(distributions)}")
    except Exception as e:
        report["errors"].append(f"Player distributions: {e}")
        report["steps"]["player_distributions"] = {"status": "ERROR", "error": str(e)}
        print(f"  ERROR: {e}")

    # Step 5: Signal validation
    print("\nStep 5: Signal Tier Validation")
    try:
        from src.intelligence.signal_validator import validate_signal_tiers
        validation = validate_signal_tiers()
        tier_summary = {
            str(tier): {
                "precision": m.get("precision"),
                "status": m.get("status"),
            }
            for tier, m in validation.get("tier_metrics", {}).items()
        }
        report["steps"]["signal_validation"] = {
            "status": "OK",
            "total_signals": validation["total_resolved_signals"],
            "overall_precision": validation["overall_precision"],
            "tier_summary": tier_summary,
        }
        print(f"  Total resolved signals: {validation['total_resolved_signals']}")
        print(f"  Overall precision: {validation['overall_precision']}")
    except Exception as e:
        report["errors"].append(f"Signal validation: {e}")
        report["steps"]["signal_validation"] = {"status": "ERROR", "error": str(e)}
        print(f"  ERROR: {e}")

    # Final report
    elapsed = round(time.time() - start_time, 1)
    report["completed_at"] = datetime.utcnow().isoformat()
    report["elapsed_seconds"] = elapsed
    report["total_errors"] = len(report["errors"])
    report["status"] = "SUCCESS" if not report["errors"] else "PARTIAL"

    RETRAINING_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(RETRAINING_REPORT_PATH, "w") as f:
        json.dump(report, f, indent=2)

    print("\n" + "=" * 60)
    print(f"RETRAINING COMPLETE in {elapsed}s")
    print(f"Status: {report['status']}")
    if report["errors"]:
        print(f"Errors: {len(report['errors'])}")
        for err in report["errors"]:
            print(f"  - {err}")
    print("=" * 60)
    return report

