"""
Spacing Validator — SESSION B
YOLOv8 player (x,y) tracking during resimulation.
Computes spacing score and validates lineup changes after hot-swap.

Graceful degradation: if ultralytics not installed, returns None spacing score
so callers continue without vision data.

Pure functions only.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
COURT_WIDTH_FEET: float = 50.0
COURT_LENGTH_FEET: float = 94.0
MIN_PLAYERS_FOR_SPACING: int = 3
IDEAL_SPACING_FEET: float = 15.0       # ideal distance between teammates
CROWDING_THRESHOLD_FEET: float = 8.0   # below this = crowded
YOLO_CONFIDENCE_THRESHOLD: float = 0.40
YOLO_MODEL_PATH: str = "data/models/yolov8n.pt"

# Spacing score bounds
SPACING_SCORE_MIN: float = 0.0
SPACING_SCORE_MAX: float = 1.0


# ---------------------------------------------------------------------------
# YOLOv8 loader — graceful degradation
# ---------------------------------------------------------------------------

def _load_yolo_model(model_path: str = YOLO_MODEL_PATH):
    """Load YOLOv8 model. Returns None if ultralytics not available."""
    try:
        from ultralytics import YOLO  # type: ignore
        if not Path(model_path).exists():
            logger.warning("YOLOv8 model not found at %s — downloading nano", model_path)
            model = YOLO("yolov8n.pt")
            Path(model_path).parent.mkdir(parents=True, exist_ok=True)
            model.save(model_path)
            return model
        return YOLO(model_path)
    except ImportError:
        logger.warning("ultralytics not installed — spacing validator disabled")
        return None


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------

def detect_players_from_frame(
    frame: np.ndarray,
    model=None,
    conf_threshold: float = YOLO_CONFIDENCE_THRESHOLD,
) -> list[dict[str, float]]:
    """
    Run YOLOv8 inference on a single frame.
    Returns list of {x, y, confidence} dicts in pixel space.

    Args:
        frame:          BGR numpy array (H×W×3)
        model:          Pre-loaded YOLO model (or None for auto-load)
        conf_threshold: Minimum detection confidence

    Returns [] if model unavailable or no players detected.
    """
    if model is None:
        model = _load_yolo_model()
    if model is None:
        return []

    try:
        results = model(frame, verbose=False)
        detections = []
        for result in results:
            boxes = result.boxes
            if boxes is None:
                continue
            for box in boxes:
                conf = float(box.conf[0])
                cls = int(box.cls[0])
                # Class 0 = person in COCO
                if cls == 0 and conf >= conf_threshold:
                    x_center = float((box.xyxy[0][0] + box.xyxy[0][2]) / 2)
                    y_center = float((box.xyxy[0][1] + box.xyxy[0][3]) / 2)
                    detections.append({"x": x_center, "y": y_center, "confidence": conf})
        return detections
    except Exception as exc:
        logger.warning("YOLOv8 inference failed: %s", exc)
        return []


def pixel_to_court_coords(
    x_px: float,
    y_px: float,
    frame_width: int,
    frame_height: int,
) -> tuple[float, float]:
    """Convert pixel coordinates to court coordinates in feet."""
    x_ft = (x_px / frame_width) * COURT_WIDTH_FEET
    y_ft = (y_px / frame_height) * COURT_LENGTH_FEET
    return x_ft, y_ft


# ---------------------------------------------------------------------------
# Spacing computation
# ---------------------------------------------------------------------------

def compute_pairwise_distances(
    positions: list[tuple[float, float]],
) -> list[float]:
    """Compute all pairwise distances between player positions."""
    distances = []
    n = len(positions)
    for i in range(n):
        for j in range(i + 1, n):
            dx = positions[i][0] - positions[j][0]
            dy = positions[i][1] - positions[j][1]
            distances.append(float(np.sqrt(dx * dx + dy * dy)))
    return distances


def compute_spacing_score(
    positions: list[tuple[float, float]],
) -> float | None:
    """
    Compute a spacing score (0–1) from player court positions.

    1.0 = ideal spacing (all players ~15 ft apart)
    0.0 = completely crowded

    Returns None if fewer than MIN_PLAYERS_FOR_SPACING positions provided.
    """
    if len(positions) < MIN_PLAYERS_FOR_SPACING:
        logger.debug(
            "Too few positions (%d) for spacing score — need %d",
            len(positions), MIN_PLAYERS_FOR_SPACING,
        )
        return None

    distances = compute_pairwise_distances(positions)
    if not distances:
        return None

    mean_dist = float(np.mean(distances))
    std_dist = float(np.std(distances))

    # Score = closeness to ideal spacing, penalized by variance
    distance_score = min(1.0, mean_dist / IDEAL_SPACING_FEET)
    crowding_penalty = min(1.0, sum(
        1 for d in distances if d < CROWDING_THRESHOLD_FEET
    ) / len(distances))
    variance_penalty = min(0.3, std_dist / IDEAL_SPACING_FEET * 0.3)

    score = distance_score * (1.0 - crowding_penalty) * (1.0 - variance_penalty)
    return round(max(SPACING_SCORE_MIN, min(SPACING_SCORE_MAX, score)), 4)


# ---------------------------------------------------------------------------
# Frame-level validator
# ---------------------------------------------------------------------------

def validate_spacing_from_frame(
    frame: np.ndarray,
    model=None,
) -> dict[str, Any]:
    """
    Full pipeline: detect → convert → score for a single frame.

    Returns:
        {
          "spacing_score": float | None,
          "player_count": int,
          "positions_ft": list[tuple],
          "mean_distance_ft": float | None,
          "crowded_pairs": int,
          "validated_at_ts": float,
          "vision_available": bool,
        }
    """
    detections = detect_players_from_frame(frame, model=model)
    vision_available = len(detections) > 0

    if not detections:
        return {
            "spacing_score": None,
            "player_count": 0,
            "positions_ft": [],
            "mean_distance_ft": None,
            "crowded_pairs": 0,
            "validated_at_ts": time.time(),
            "vision_available": False,
        }

    h, w = frame.shape[:2]
    positions_ft = [
        pixel_to_court_coords(d["x"], d["y"], w, h)
        for d in detections
    ]

    spacing_score = compute_spacing_score(positions_ft)
    distances = compute_pairwise_distances(positions_ft)
    mean_dist = float(np.mean(distances)) if distances else None
    crowded_pairs = sum(1 for d in distances if d < CROWDING_THRESHOLD_FEET)

    return {
        "spacing_score": spacing_score,
        "player_count": len(detections),
        "positions_ft": positions_ft,
        "mean_distance_ft": round(mean_dist, 2) if mean_dist else None,
        "crowded_pairs": crowded_pairs,
        "validated_at_ts": time.time(),
        "vision_available": True,
    }


# ---------------------------------------------------------------------------
# Hot-swap spacing comparison
# ---------------------------------------------------------------------------

def compare_pre_post_swap_spacing(
    pre_swap_score: float | None,
    post_swap_score: float | None,
) -> dict[str, Any]:
    """
    Compare spacing scores before and after a roster hot-swap.
    Returns analysis dict for inclusion in Tier 1 alert payload.
    """
    if pre_swap_score is None or post_swap_score is None:
        return {
            "spacing_delta": None,
            "spacing_improved": None,
            "vision_data_available": False,
        }

    delta = post_swap_score - pre_swap_score
    return {
        "spacing_delta": round(delta, 4),
        "spacing_improved": delta > 0,
        "pre_swap_spacing": pre_swap_score,
        "post_swap_spacing": post_swap_score,
        "vision_data_available": True,
    }


def build_spacing_alert_payload(
    spacing_result: dict[str, Any],
    sim_result: dict[str, Any],
    injury_signal: dict[str, Any],
) -> dict[str, Any]:
    """
    Build the full Tier 1 alert payload with spacing score included.
    This is the payload emitted via WebSocket when WP diverges >8%.
    """
    return {
        "alert_tier": 1,
        "alert_type": "INJURY_HOT_SWAP_WP_DIVERGENCE",
        "player_name": injury_signal.get("player_name"),
        "injury_source": injury_signal.get("source"),
        "injury_tier": injury_signal.get("tier"),
        "win_probability": sim_result.get("win_probability"),
        "market_win_prob": sim_result.get("market_win_prob"),
        "wp_divergence": sim_result.get("wp_divergence"),
        "swap_wp_delta": sim_result.get("swap_wp_delta"),
        "spacing_score": spacing_result.get("spacing_score"),
        "spacing_delta": spacing_result.get("spacing_delta"),
        "player_count_detected": spacing_result.get("player_count", 0),
        "vision_available": spacing_result.get("vision_available", False),
        "sim_iterations": sim_result.get("iterations", 200),
        "sim_method": sim_result.get("method", "fast_quantum_mc"),
        "emitted_at_ts": time.time(),
    }
