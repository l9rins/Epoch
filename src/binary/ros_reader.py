"""
Epoch Engine — .ROS Binary Reader

Read, validate, and parse NBA 2K14 .ROS files into structured Player objects.
All offsets imported from constants.py — no magic numbers.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .constants import (
    CRC_OFFSET,
    HOT_ZONE_BYTES,
    NUM_HOT_ZONES,
    NUM_RECORDS,
    NUM_SIG_SLOTS,
    NUM_SKILLS,
    NUM_TENDENCIES,
    NUM_TENDENCIES_TOTAL,
    NAME_POOL_START,
    NAME_POOL_END,
    PLAYERS_PER_RECORD,
    compute_crc,
    hot_zone_byte_offset,
    hz_unpack,
    is_boundary_record,
    player_data_offset,
    read_height,
    read_stored_crc,
    read_team_id,
    read_weight,
    sig_skill_byte_offset,
    skill_byte_offset,
    skill_decode,
    tendency_byte_offset,
    tend_decode,
    validate_crc,
)


class RosCorruptionError(Exception):
    """Raised when the .ROS file is corrupt or invalid."""
    pass


@dataclass
class Player:
    """A single parsed player from the .ROS file."""

    # Identity
    record_idx: int
    sub_idx: int              # 0 = EVEN, 1 = ODD
    name: str = ""

    # Physical
    height: float = 0.0       # inches
    weight: float = 0.0       # lbs
    team_id: int = 0

    # Skills (42 decoded ratings, 25–110+)
    skills: list[int] = field(default_factory=list)

    # Tendencies (57 active values, 0–99)
    tendencies: list[int] = field(default_factory=list)

    # Internal tendencies (indices 57–68, preserved but read-only)
    tendencies_internal: list[int] = field(default_factory=list)

    # Hot zones (14 values, 0–3)
    hot_zones: list[int] = field(default_factory=list)

    # Signature skills (5 slots, each 0–44)
    sig_skills: list[int] = field(default_factory=list)

    @property
    def overall(self) -> int:
        """Decoded OVR rating (skill index 0)."""
        return self.skills[0] if self.skills else 0

    @property
    def is_boundary(self) -> bool:
        """True if this player is in a boundary record."""
        return is_boundary_record(self.record_idx)


def load_ros(path: str | Path) -> bytearray:
    """Load a .ROS file into a mutable bytearray.

    Returns:
        Mutable bytearray of the entire file contents.

    Raises:
        FileNotFoundError: If the file doesn't exist.
        RosCorruptionError: If the file is too small to contain a valid header.
    """
    path = Path(path)
    data = bytearray(path.read_bytes())

    if len(data) < 8:
        raise RosCorruptionError(f"File too small ({len(data)} bytes) — not a valid .ROS")

    return data


def check_crc(data: bytes | bytearray, *, raise_on_fail: bool = True) -> bool:
    """Validate the CRC of a .ROS buffer.

    Args:
        data: The full .ROS buffer.
        raise_on_fail: If True, raise RosCorruptionError on mismatch.

    Returns:
        True if CRC is valid.

    Raises:
        RosCorruptionError: If CRC doesn't match and raise_on_fail is True.
    """
    stored = read_stored_crc(data)
    computed = compute_crc(data)

    if stored != computed:
        if raise_on_fail:
            raise RosCorruptionError(
                f"CRC mismatch: stored=0x{stored:08X}, computed=0x{computed:08X}"
            )
        return False
    return True


def read_player(
    data: bytes | bytearray,
    record_idx: int,
    sub_idx: int,
    name_pool: Optional[dict[tuple[int, int], str]] = None,
) -> Player:
    """Parse a single player from the .ROS buffer.

    Args:
        data: The full .ROS buffer.
        record_idx: Record index (0–831).
        sub_idx: 0 for EVEN, 1 for ODD.
        name_pool: Optional pre-built name lookup dict.

    Returns:
        Parsed Player dataclass.
    """
    player = Player(record_idx=record_idx, sub_idx=sub_idx)

    # Physical measurements
    try:
        player.height = read_height(data, record_idx, sub_idx)
        player.weight = read_weight(data, record_idx, sub_idx)
        player.team_id = read_team_id(data, record_idx, sub_idx)
    except (struct.error, IndexError) as e:
        raise RosCorruptionError(
            f"Failed reading physical data for record {record_idx} sub {sub_idx}: {e}"
        )

    # Skills (42 fields)
    player.skills = []
    for i in range(NUM_SKILLS):
        off = skill_byte_offset(record_idx, sub_idx, i)
        if off >= len(data):
            raise RosCorruptionError(
                f"Skill offset {off} beyond file end for record {record_idx} sub {sub_idx} skill {i}"
            )
        player.skills.append(skill_decode(data[off]))

    # Tendencies — active (0–56)
    player.tendencies = []
    for i in range(NUM_TENDENCIES):
        off = tendency_byte_offset(record_idx, sub_idx, i)
        if off >= len(data):
            raise RosCorruptionError(
                f"Tendency offset {off} beyond file end for record {record_idx} sub {sub_idx} tend {i}"
            )
        player.tendencies.append(tend_decode(data[off]))

    # Tendencies — engine internal (57–68), read-only
    player.tendencies_internal = []
    for i in range(NUM_TENDENCIES, NUM_TENDENCIES_TOTAL):
        off = tendency_byte_offset(record_idx, sub_idx, i)
        if off >= len(data):
            break  # Graceful — these are optional/internal
        player.tendencies_internal.append(data[off])

    # Hot zones (14 zones from 4 bytes)
    hz_off = hot_zone_byte_offset(record_idx, sub_idx)
    if hz_off + HOT_ZONE_BYTES <= len(data):
        player.hot_zones = hz_unpack(data[hz_off:hz_off + HOT_ZONE_BYTES])
    else:
        player.hot_zones = [1] * NUM_HOT_ZONES  # Default to neutral

    # Signature skills (5 slots)
    player.sig_skills = []
    for i in range(NUM_SIG_SLOTS):
        off = sig_skill_byte_offset(record_idx, sub_idx, i)
        if off >= len(data):
            player.sig_skills.append(0)
        else:
            player.sig_skills.append(data[off])

    # Name
    if name_pool and (record_idx, sub_idx) in name_pool:
        player.name = name_pool[(record_idx, sub_idx)]

    return player


def read_all_players(
    data: bytes | bytearray,
    name_pool: Optional[dict[tuple[int, int], str]] = None,
) -> list[Player]:
    """Parse all 1,664 players from the .ROS buffer.

    Args:
        data: The full .ROS buffer.
        name_pool: Optional pre-built name lookup dict.

    Returns:
        List of Player objects (up to 1,664).
    """
    players = []
    for rec_idx in range(NUM_RECORDS):
        for sub in range(PLAYERS_PER_RECORD):
            try:
                player = read_player(data, rec_idx, sub, name_pool)
                players.append(player)
            except RosCorruptionError:
                # Skip corrupt records but continue parsing
                continue
    return players


def build_name_pool(data: bytes | bytearray) -> dict[tuple[int, int], str]:
    """Build a name lookup dictionary from the string pool.

    The name pool at 0x25ED40–0x28B7DF contains UTF-16 LE encoded strings.
    This returns a dict mapping (record_idx, sub_idx) → player name.

    NOTE: The exact mapping algorithm depends on pointer table structure
    which varies by .ROS version. This is a basic implementation that
    reads null-terminated UTF-16 LE strings sequentially.
    """
    pool: dict[tuple[int, int], str] = {}

    if len(data) < NAME_POOL_END:
        return pool  # File too small for name pool

    # Read raw string pool bytes
    pool_bytes = data[NAME_POOL_START:NAME_POOL_END]

    # Parse null-terminated UTF-16 LE strings
    strings: list[str] = []
    current = bytearray()

    for i in range(0, len(pool_bytes) - 1, 2):
        char = pool_bytes[i:i + 2]
        if char == b'\x00\x00':
            if current:
                try:
                    strings.append(current.decode('utf-16-le'))
                except UnicodeDecodeError:
                    strings.append("")
                current = bytearray()
        else:
            current.extend(char)

    # Map strings to player slots — this uses a simple sequential assumption.
    # The real mapping may use pointer tables; refine with actual .ROS analysis.
    for idx, name in enumerate(strings):
        if idx >= NUM_RECORDS * PLAYERS_PER_RECORD:
            break
        record_idx = idx // PLAYERS_PER_RECORD
        sub_idx = idx % PLAYERS_PER_RECORD
        pool[(record_idx, sub_idx)] = name

    return pool
