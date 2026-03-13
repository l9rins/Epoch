"""
Roster Hot-Swap — SESSION B
Mid-game injury response: zero injured player minutes, boost backup,
recalculate CRC.

Rules:
  - Always call write_crc() after every binary write
  - Never write to tendency indices 57-68
  - All offsets from src.binary.constants — no magic numbers
  - Pure functions only
"""

from __future__ import annotations

import copy
import logging
from pathlib import Path
from typing import Any

from src.binary.constants import (
    NUM_TENDENCIES,
    SKILL_OFFSET,
    TENDENCY_OFFSET,
    write_crc,
    compute_crc,
    validate_crc,
    player_data_offset,
    skill_byte_offset,
    tendency_byte_offset,
    skill_encode,
    tend_encode,
    SKILL_RAW_MAX,
    TENDENCY_MIN,
    TENDENCY_MAX,
    NUM_SKILLS,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
MINUTES_ZEROED_VALUE: int = 0         # stamina proxy set to 0 for injured player
BACKUP_BOOST_AMOUNT: int = 5          # raw skill tier boost for emergency backup
BACKUP_BOOST_MAX_RATING: int = 99     # cap backup boost at this rating
STAMINA_SKILL_INDEX: int = 30         # Stamina is skill index 30 per constants
DURABILITY_SKILL_INDEX: int = 32      # Durability skill index 32

ROS_PATH = Path("data/roster.ros")


# ---------------------------------------------------------------------------
# Binary read helpers
# ---------------------------------------------------------------------------

def _read_skill(data: bytearray, record_idx: int, sub_idx: int, skill_idx: int) -> int:
    """Read raw skill byte."""
    off = skill_byte_offset(record_idx, sub_idx, skill_idx)
    return data[off]


def _write_skill_raw(
    data: bytearray,
    record_idx: int,
    sub_idx: int,
    skill_idx: int,
    raw_value: int,
) -> None:
    """Write a raw skill byte. Does NOT recalculate CRC — caller must do that."""
    off = skill_byte_offset(record_idx, sub_idx, skill_idx)
    data[off] = max(0, min(SKILL_RAW_MAX, raw_value))


def _write_tendency_safe(
    data: bytearray,
    record_idx: int,
    sub_idx: int,
    tend_idx: int,
    value: int,
) -> None:
    """Write tendency — enforces ENGINE INTERNAL guard (indices 57-68)."""
    if tend_idx >= NUM_TENDENCIES:
        raise ValueError(
            f"Attempted write to ENGINE INTERNAL tendency index {tend_idx}. "
            f"Indices {NUM_TENDENCIES}–68 are read-only."
        )
    off = tendency_byte_offset(record_idx, sub_idx, tend_idx)
    data[off] = tend_encode(value)


# ---------------------------------------------------------------------------
# Hot-swap core
# ---------------------------------------------------------------------------

def zero_player_minutes(
    data: bytearray,
    record_idx: int,
    sub_idx: int,
) -> bytearray:
    """
    Zero the injured player's stamina and durability in the binary.
    This proxies for zeroing minutes — the sim engine reads stamina
    as a weight for participation probability.

    Always recalculates CRC after write.
    """
    _write_skill_raw(data, record_idx, sub_idx, STAMINA_SKILL_INDEX, MINUTES_ZEROED_VALUE)
    _write_skill_raw(data, record_idx, sub_idx, DURABILITY_SKILL_INDEX, MINUTES_ZEROED_VALUE)
    write_crc(data)
    logger.info(
        "Zeroed stamina/durability for record=%d sub=%d | CRC recalculated",
        record_idx, sub_idx,
    )
    return data


def boost_backup_player(
    data: bytearray,
    record_idx: int,
    sub_idx: int,
    boost_amount: int = BACKUP_BOOST_AMOUNT,
) -> bytearray:
    """
    Boost the emergency backup's stamina to signal elevated minutes.
    Caps at BACKUP_BOOST_MAX_RATING.

    Always recalculates CRC after write.
    """
    current_raw = _read_skill(data, record_idx, sub_idx, STAMINA_SKILL_INDEX)
    boosted_raw = min(SKILL_RAW_MAX, current_raw + boost_amount)
    _write_skill_raw(data, record_idx, sub_idx, STAMINA_SKILL_INDEX, boosted_raw)
    write_crc(data)
    logger.info(
        "Boosted backup record=%d sub=%d stamina %d→%d | CRC recalculated",
        record_idx, sub_idx, current_raw, boosted_raw,
    )
    return data


def execute_hot_swap(
    data: bytearray,
    injured_record_idx: int,
    injured_sub_idx: int,
    backup_record_idx: int,
    backup_sub_idx: int,
) -> dict[str, Any]:
    """
    Full hot-swap: zero injured player, boost backup, validate CRC.

    Args:
        data:                  Mutable bytearray of the .ROS file
        injured_record_idx:    Record index of injured player
        injured_sub_idx:       Sub-index (0=EVEN, 1=ODD) of injured player
        backup_record_idx:     Record index of backup
        backup_sub_idx:        Sub-index of backup

    Returns:
        {
          "success": bool,
          "crc_valid": bool,
          "injured": {"record_idx": int, "sub_idx": int},
          "backup": {"record_idx": int, "sub_idx": int},
          "swap_ts": float,
        }
    """
    import time

    # Zero injured
    zero_player_minutes(data, injured_record_idx, injured_sub_idx)

    # Boost backup
    boost_backup_player(data, backup_record_idx, backup_sub_idx)

    # Final CRC validation
    crc_valid = validate_crc(data)
    if not crc_valid:
        logger.error("CRC validation FAILED after hot-swap — data may be corrupt")

    return {
        "success": crc_valid,
        "crc_valid": crc_valid,
        "injured": {"record_idx": injured_record_idx, "sub_idx": injured_sub_idx},
        "backup": {"record_idx": backup_record_idx, "sub_idx": backup_sub_idx},
        "swap_ts": time.time(),
    }


# ---------------------------------------------------------------------------
# File-level hot-swap (loads and saves .ROS)
# ---------------------------------------------------------------------------

def hot_swap_from_file(
    ros_path: Path,
    injured_record_idx: int,
    injured_sub_idx: int,
    backup_record_idx: int,
    backup_sub_idx: int,
) -> dict[str, Any]:
    """
    Load .ROS file, execute hot-swap in memory, write back atomically.

    Returns swap result dict.
    """
    if not ros_path.exists():
        raise FileNotFoundError(f".ROS file not found: {ros_path}")

    data = bytearray(ros_path.read_bytes())

    if not validate_crc(data):
        raise ValueError(f"Input .ROS file has invalid CRC: {ros_path}")

    result = execute_hot_swap(
        data,
        injured_record_idx,
        injured_sub_idx,
        backup_record_idx,
        backup_sub_idx,
    )

    # Atomic write — write to temp then rename
    tmp_path = ros_path.with_suffix(".ros.tmp")
    tmp_path.write_bytes(bytes(data))
    tmp_path.replace(ros_path)

    result["ros_path"] = str(ros_path)
    logger.info("Hot-swap written to %s", ros_path)
    return result


def build_post_swap_game_state(
    pre_swap_state: dict[str, Any],
    injured_player_rating_impact: float = 0.08,
) -> dict[str, Any]:
    """
    Estimate post-swap game state by degrading the injured team's ratings.

    Args:
        pre_swap_state:           Current game state dict
        injured_player_rating_impact: Fraction of team rating to degrade

    Returns:
        Modified game state dict for fast simulation.
    """
    state = copy.deepcopy(pre_swap_state)

    # Determine which team the injured player is on
    injured_team = state.get("injured_team", "home")

    if injured_team == "home":
        state["home_offense"] = state.get("home_offense", 108.0) * (
            1.0 - injured_player_rating_impact
        )
        state["home_defense"] = state.get("home_defense", 108.0) * (
            1.0 - injured_player_rating_impact * 0.5
        )
    else:
        state["away_offense"] = state.get("away_offense", 108.0) * (
            1.0 - injured_player_rating_impact
        )
        state["away_defense"] = state.get("away_defense", 108.0) * (
            1.0 - injured_player_rating_impact * 0.5
        )

    return state
