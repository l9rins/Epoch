"""
Epoch Engine — .ROS Binary Writer

Write modified player data back to .ROS buffer, recalculate CRC, and save.
All offsets imported from constants.py — no magic numbers.

CRITICAL RULES:
- NEVER write to tendency indices 57–68 (engine-internal)
- ALWAYS recalculate CRC after any write
- ALWAYS check boundary records before writing TeamID
"""

from __future__ import annotations

import struct
from pathlib import Path
from typing import Optional

from .constants import (
    HOT_ZONE_BYTES,
    NUM_HOT_ZONES,
    NUM_SIG_SLOTS,
    NUM_SKILLS,
    NUM_TENDENCIES,
    NUM_TENDENCIES_TOTAL,
    OFF_HEIGHT,
    OFF_TEAM_ID,
    OFF_WEIGHT,
    SKILL_RAW_MAX,
    TENDENCY_MAX,
    TENDENCY_MIN,
    hot_zone_byte_offset,
    hz_pack,
    hz_unpack,
    is_boundary_record,
    player_data_offset,
    sig_skill_byte_offset,
    skill_byte_offset,
    skill_encode,
    tendency_byte_offset,
    tend_encode,
    write_crc,
)
from .ros_reader import Player, RosCorruptionError


class BoundaryRecordError(Exception):
    """Raised when a write would corrupt a boundary record's shared data."""
    pass


# ═════════════════════════════════════════════════════════════════════════════
# SINGLE-FIELD WRITERS
# ═════════════════════════════════════════════════════════════════════════════

def write_skill(
    data: bytearray,
    record_idx: int,
    sub_idx: int,
    skill_idx: int,
    rating: int,
    *,
    auto_crc: bool = True,
) -> None:
    """Write a single skill rating to the buffer.

    Args:
        data: Mutable .ROS buffer.
        record_idx: Record index (0–831).
        sub_idx: 0 for EVEN, 1 for ODD.
        skill_idx: Skill index (0–41). Index 41 (Overall_I) is blocked.
        rating: Decoded rating (25–110).
        auto_crc: If True, recalculate CRC after write.

    Raises:
        ValueError: If skill_idx is 41 (Overall_I — must never be overwritten).
    """
    if skill_idx == 41:
        raise ValueError(
            "Cannot write to skill index 41 (Overall_I) — "
            "this field is always 1 in .ROS and must not be overwritten from CSV."
        )

    raw = skill_encode(rating)
    off = skill_byte_offset(record_idx, sub_idx, skill_idx)
    data[off] = raw

    if auto_crc:
        write_crc(data)


def write_tendency(
    data: bytearray,
    record_idx: int,
    sub_idx: int,
    tend_idx: int,
    value: int,
    *,
    auto_crc: bool = True,
) -> None:
    """Write a single tendency value to the buffer.

    Args:
        data: Mutable .ROS buffer.
        record_idx: Record index (0–831).
        sub_idx: 0 for EVEN, 1 for ODD.
        tend_idx: Tendency index (0–56 only). 57–68 are engine-internal and blocked.
        value: Tendency value (0–99).
        auto_crc: If True, recalculate CRC after write.

    Raises:
        ValueError: If tend_idx is >= 57 (engine-internal tendencies).
    """
    if tend_idx >= NUM_TENDENCIES:
        raise ValueError(
            f"Cannot write to tendency index {tend_idx} — "
            f"indices {NUM_TENDENCIES}–{NUM_TENDENCIES_TOTAL - 1} are engine-internal. "
            f"Only indices 0–{NUM_TENDENCIES - 1} are writable."
        )

    raw = tend_encode(value)
    off = tendency_byte_offset(record_idx, sub_idx, tend_idx)
    data[off] = raw

    if auto_crc:
        write_crc(data)


def write_hot_zones(
    data: bytearray,
    record_idx: int,
    sub_idx: int,
    zones: list[int],
    *,
    auto_crc: bool = True,
) -> None:
    """Write all 14 hot zone values to the buffer.

    Args:
        data: Mutable .ROS buffer.
        record_idx: Record index (0–831).
        sub_idx: 0 for EVEN, 1 for ODD.
        zones: List of 14 values (0–3 each).
        auto_crc: If True, recalculate CRC after write.
    """
    packed = hz_pack(zones)
    off = hot_zone_byte_offset(record_idx, sub_idx)
    data[off:off + HOT_ZONE_BYTES] = packed

    if auto_crc:
        write_crc(data)


def write_hot_zone(
    data: bytearray,
    record_idx: int,
    sub_idx: int,
    hz_idx: int,
    value: int,
    *,
    auto_crc: bool = True,
) -> None:
    """Write a single hot zone value (read-modify-write the packed block).

    Args:
        data: Mutable .ROS buffer.
        record_idx: Record index (0–831).
        sub_idx: 0 for EVEN, 1 for ODD.
        hz_idx: Hot zone index (0–13).
        value: Hot zone value (0–3).
        auto_crc: If True, recalculate CRC after write.
    """
    if not (0 <= hz_idx < NUM_HOT_ZONES):
        raise ValueError(f"hz_idx {hz_idx} out of range 0–{NUM_HOT_ZONES - 1}")
    if not (0 <= value <= 3):
        raise ValueError(f"Hot zone value {value} out of range 0–3")

    # Read current packed zones, modify one, write back
    off = hot_zone_byte_offset(record_idx, sub_idx)
    current = hz_unpack(data[off:off + HOT_ZONE_BYTES])
    current[hz_idx] = value
    packed = hz_pack(current)
    data[off:off + HOT_ZONE_BYTES] = packed

    if auto_crc:
        write_crc(data)


def write_sig_skill(
    data: bytearray,
    record_idx: int,
    sub_idx: int,
    slot_idx: int,
    skill_id: int,
    *,
    auto_crc: bool = True,
) -> None:
    """Write a single signature skill slot.

    Args:
        data: Mutable .ROS buffer.
        record_idx: Record index (0–831).
        sub_idx: 0 for EVEN, 1 for ODD.
        slot_idx: Signature skill slot (0–4).
        skill_id: Signature skill ID (0–44).
        auto_crc: If True, recalculate CRC after write.
    """
    off = sig_skill_byte_offset(record_idx, sub_idx, slot_idx)
    data[off] = skill_id

    if auto_crc:
        write_crc(data)


def write_team_id(
    data: bytearray,
    record_idx: int,
    sub_idx: int,
    team_id: int,
    *,
    auto_crc: bool = True,
    force_boundary: bool = False,
) -> None:
    """Write TeamID for a player, with boundary record safety check.

    Args:
        data: Mutable .ROS buffer.
        record_idx: Record index (0–831).
        sub_idx: 0 for EVEN, 1 for ODD.
        team_id: Team ID byte (0–255).
        auto_crc: If True, recalculate CRC after write.
        force_boundary: If True, allow writing to boundary records (dangerous).

    Raises:
        BoundaryRecordError: If this is a boundary record and force_boundary is False.
    """
    if is_boundary_record(record_idx) and not force_boundary:
        raise BoundaryRecordError(
            f"Record {record_idx} is a boundary record — EVEN+ODD share TeamID byte. "
            f"Writing TeamID would affect both players. Set force_boundary=True to override."
        )

    base = player_data_offset(record_idx, sub_idx)
    data[base + OFF_TEAM_ID] = team_id

    if auto_crc:
        write_crc(data)


def write_height(
    data: bytearray,
    record_idx: int,
    sub_idx: int,
    height_inches: float,
    *,
    auto_crc: bool = True,
) -> None:
    """Write height (Float32 Big-Endian) in inches."""
    base = player_data_offset(record_idx, sub_idx)
    struct.pack_into(">f", data, base + OFF_HEIGHT, height_inches)
    if auto_crc:
        write_crc(data)


def write_weight(
    data: bytearray,
    record_idx: int,
    sub_idx: int,
    weight_lbs: float,
    *,
    auto_crc: bool = True,
) -> None:
    """Write weight (Float32 Big-Endian) in lbs."""
    base = player_data_offset(record_idx, sub_idx)
    struct.pack_into(">f", data, base + OFF_WEIGHT, weight_lbs)
    if auto_crc:
        write_crc(data)


# ═════════════════════════════════════════════════════════════════════════════
# BULK WRITER
# ═════════════════════════════════════════════════════════════════════════════

def write_player(
    data: bytearray,
    player: Player,
    *,
    auto_crc: bool = True,
    skip_overall_i: bool = True,
) -> None:
    """Write all fields of a Player back to the buffer.

    Args:
        data: Mutable .ROS buffer.
        player: Player dataclass with updated field values.
        auto_crc: If True, recalculate CRC after all writes.
        skip_overall_i: If True, skip skill index 41 (Overall_I).
    """
    rec = player.record_idx
    sub = player.sub_idx

    # Physical measurements
    write_height(data, rec, sub, player.height, auto_crc=False)
    write_weight(data, rec, sub, player.weight, auto_crc=False)

    # Skills (skip index 41 = Overall_I by default)
    for i, rating in enumerate(player.skills):
        if skip_overall_i and i == 41:
            continue
        if i >= NUM_SKILLS:
            break
        raw = skill_encode(rating)
        off = skill_byte_offset(rec, sub, i)
        data[off] = raw

    # Tendencies (active only, 0–56)
    for i, value in enumerate(player.tendencies):
        if i >= NUM_TENDENCIES:
            break
        raw = tend_encode(value)
        off = tendency_byte_offset(rec, sub, i)
        data[off] = raw

    # Hot zones
    if len(player.hot_zones) == NUM_HOT_ZONES:
        packed = hz_pack(player.hot_zones)
        off = hot_zone_byte_offset(rec, sub)
        data[off:off + HOT_ZONE_BYTES] = packed

    # Signature skills
    for i, skill_id in enumerate(player.sig_skills):
        if i >= NUM_SIG_SLOTS:
            break
        off = sig_skill_byte_offset(rec, sub, i)
        data[off] = skill_id

    # CRC — one recalculation at the end
    if auto_crc:
        write_crc(data)


# ═════════════════════════════════════════════════════════════════════════════
# CRC & SAVE
# ═════════════════════════════════════════════════════════════════════════════

def recalculate_crc(data: bytearray) -> int:
    """Recalculate and write CRC. Returns the new CRC value."""
    write_crc(data)
    return struct.unpack(">I", data[0:4])[0]


def save_ros(data: bytearray, path: str | Path) -> None:
    """Recalculate CRC and save the buffer to disk.

    Args:
        data: Mutable .ROS buffer.
        path: Output file path.
    """
    write_crc(data)
    Path(path).write_bytes(bytes(data))
