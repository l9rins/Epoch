"""
Epoch Engine — Binary Constants & Codecs

All field offsets, codec functions, CRC helpers, and label arrays for the
NBA 2K14 .ROS binary roster file format.

Rule: NO magic numbers anywhere else in the codebase. Import from here.
"""

import struct
import zlib
from typing import Optional

# ─────────────────────────────────────────────────────────────────────────────
# File-level constants
# ─────────────────────────────────────────────────────────────────────────────

CRC_OFFSET = 0x0000            # Big-Endian uint32 CRC stored here
CRC_DATA_START = 4             # CRC is computed over data[4:]
NAME_POOL_START = 0x25ED40     # UTF-16 LE string pool starts here
NAME_POOL_END = 0x28B7DF       # UTF-16 LE string pool ends here
TOC_START = 0x0020             # Table of contents (40 embedded CSVs)
TOC_END = 0x01FF

# ─────────────────────────────────────────────────────────────────────────────
# Record layout
# ─────────────────────────────────────────────────────────────────────────────

NUM_RECORDS = 832              # Primary roster records
PLAYERS_PER_RECORD = 2         # EVEN (sub_idx=0) + ODD (sub_idx=1)
TOTAL_PLAYERS = NUM_RECORDS * PLAYERS_PER_RECORD  # 1664

# Record size — the stride between consecutive primary records in the file.
# Each record holds two players (EVEN at standard layout, ODD nibble-shifted).
RECORD_SIZE = 0x390            # 912 bytes per record

# Where in the file the roster data begins (after header + TOC).
ROSTER_DATA_START = 0x0480     # First player record offset

# ─────────────────────────────────────────────────────────────────────────────
# Player offsets within a record
# ─────────────────────────────────────────────────────────────────────────────

# EVEN player (sub_idx=0): standard layout — offsets are relative to record start
# ODD  player (sub_idx=1): nibble-shifted — data starts at +0x1C7 within record

ODD_NIBBLE_SHIFT = 0x1C7       # ODD player data offset within record

# Physical measurements (Float32 Big-Endian, relative to player data start)
OFF_HEIGHT = 0x000             # Height in inches (Float32 BE)
OFF_WEIGHT = 0x004             # Weight in lbs (Float32 BE)

# Team
OFF_TEAM_ID = 0x00B            # Single byte — TeamID

# Birth date — bit-packed starting at bit 149 relative to player data start
BIRTHDATE_BIT_OFFSET = 149

# ─────────────────────────────────────────────────────────────────────────────
# Skill fields (42 fields, tier 0–13)
# ─────────────────────────────────────────────────────────────────────────────

# Relative offset of the first skill byte within a player's data block.
SKILL_OFFSET = 548             # 0x224
NUM_SKILLS = 42
SKILL_MIN_TIER = 0
SKILL_MAX_TIER = 13
SKILL_RAW_MAX = 255            # Supports modded players up to rating 110

SKILL_LABELS = [
    # Core (0–4)
    "Overall",          # 0
    "Inside Scoring",   # 1
    "Mid-Range",        # 2
    "3PT Shooting",     # 3
    "Free Throw",       # 4
    # Finish (5–9)
    "Layup",            # 5
    "Standing Dunk",    # 6
    "Driving Dunk",     # 7
    "Post Hook",        # 8
    "Post Fadeaway",    # 9
    # Offense (10–17)
    "Post Control",     # 10
    "Draw Foul",        # 11
    "Hands",            # 12
    "Ball Control",     # 13
    "Passing IQ",       # 14
    "Passing Accuracy", # 15
    "Off Dribble Mid",  # 16
    "Off Dribble 3PT",  # 17
    # Defense (18–25)
    "On-Ball Defense",  # 18
    "Steal",            # 19
    "Block",            # 20
    "Shot Contest",     # 21
    "Lateral Quickness",# 22
    "Help Defense IQ",  # 23
    "Pass Perception",  # 24
    "Pick & Roll Def.", # 25
    # Athletic (26–33)
    "Speed",            # 26
    "Acceleration",     # 27
    "Vertical",         # 28
    "Strength",         # 29
    "Stamina",          # 30
    "Hustle",           # 31
    "Durability",       # 32
    "Quickness",        # 33
    # Other (34–41)
    "Offensive Rebound",# 34
    "Defensive Rebound",# 35
    "Offensive Awareness",# 36
    "Defensive Awareness",# 37
    "Consistency",      # 38
    "Potential",        # 39
    "Intangibles",      # 40
    "Overall_I",        # 41 — always 1 in ROS; NEVER overwrite from CSV
]

# ─────────────────────────────────────────────────────────────────────────────
# Tendency fields (57 active + 12 engine-internal = 69 total)
# ─────────────────────────────────────────────────────────────────────────────

TENDENCY_OFFSET = 591          # 0x24F
NUM_TENDENCIES = 57            # Active tendencies (writable)
NUM_TENDENCIES_INTERNAL = 12   # Engine-internal (indices 57–68) — NEVER write
NUM_TENDENCIES_TOTAL = 69      # Total stored in binary
TENDENCY_MIN = 0
TENDENCY_MAX = 99

TENDENCY_LABELS = [
    # Scoring tendencies (0–14)
    "Step Through Shot",    # 0
    "Shot Under Basket",    # 1
    "Shot Close",           # 2
    "Shot Close Left",      # 3
    "Shot Close Middle",    # 4
    "Shot Close Right",     # 5
    "Shot Mid-Range",       # 6
    "Shot Left",            # 7
    "Shot Left Center",     # 8
    "Shot Center",          # 9
    "Shot Right Center",    # 10
    "Shot Right",           # 11
    "Shot 3PT",             # 12
    "Shot 3PT Left",        # 13
    "Shot 3PT Center",      # 14
    # More scoring (15–24)
    "Shot 3PT Right",       # 15
    "Contested Jumper",     # 16
    "Contested 3PT",        # 17
    "Stepback Jumper",      # 18
    "Spin Jumper",          # 19
    "Transition Pull-up",   # 20
    "Drive Pull-up",        # 21
    "Use Glass",            # 22
    "Driving Layup",        # 23
    "Driving Dunk",         # 24
    # Post & passing (25–34)
    "Flashy Dunk",          # 25
    "Alley-Oop",            # 26
    "Putback Dunk",         # 27
    "Crash Offensive",      # 28
    "Crash Defensive",      # 29
    "Post Up",              # 30
    "Post Hook",            # 31
    "Post Fade",            # 32
    "Post Shimmy Shot",     # 33
    "Post Face Up",         # 34
    # More tendencies (35–49)
    "Post Drive",           # 35
    "Post Spin",            # 36
    "Post Drop Step",       # 37
    "Post Hop Step",        # 38
    "Passing",              # 39
    "Lob Pass",             # 40
    "Flashy Pass",          # 41
    "Alley-Oop Pass",       # 42
    "Iso vs Left",          # 43
    "Iso vs Right",         # 44
    "Roll vs Pop",          # 45
    "Transition Spot Up",   # 46
    "On-Ball Screen",       # 47
    "Foul",                 # 48
    "Hard Foul",            # 49
    # Defense (50–56)
    "Take Charge",          # 50
    "On-Ball Steal",        # 51
    "Contest Shot",         # 52
    "Block Shot",           # 53
    "Foul Shooting",        # 54
    "Def Rotation",         # 55
    "Hands Up Defense",     # 56
]

# ─────────────────────────────────────────────────────────────────────────────
# Hot zones (14 zones, 2-bit packed)
# ─────────────────────────────────────────────────────────────────────────────

HOT_ZONE_OFFSET = 660         # 0x294
HOT_ZONE_BYTES = 4             # 14 zones × 2 bits = 28 bits = 4 bytes
NUM_HOT_ZONES = 14
HZ_COLD = 0
HZ_NEUTRAL = 1
HZ_HOT = 2
HZ_BURNED = 3                 # a.k.a. "Very Hot"

HZ_LABELS = [
    "Close Left",           # 0
    "Close Right",          # 1
    "Close Center",         # 2
    "Mid Left",             # 3
    "Mid Left Center",      # 4
    "Mid Center",           # 5
    "Mid Right Center",     # 6
    "Mid Right",            # 7
    "3PT Left",             # 8
    "3PT Left Center",      # 9
    "3PT Center",           # 10
    "3PT Right Center",     # 11
    "3PT Right",            # 12
    "Under Basket",         # 13
]

# ─────────────────────────────────────────────────────────────────────────────
# Signature skills (5 slots, 41 entries from RED MC 2K14 Enums)
# ─────────────────────────────────────────────────────────────────────────────

SIG_SKILL_OFFSET = 685        # 0x2AD — 5 consecutive bytes
NUM_SIG_SLOTS = 5
SIG_SKILL_NONE = 0

SIG_SKILL_NAMES = [
    "None",                     # 0
    "Posterizer",               # 1
    "Highlight Film",           # 2
    "Acrobat",                  # 3
    "Finisher",                 # 4
    "Fierce Competitor",        # 5
    "Deadeye",                  # 6
    "Corner Specialist",        # 7
    "Microwave",                # 8
    "Volume Shooter",           # 9
    "Shot Creator",             # 10
    "Spot Up Shooter",          # 11
    "Screen Outlet",            # 12
    "Floor General",            # 13
    "Dimer",                    # 14
    "Lob City Passer",          # 15
    "Lob City Finisher",        # 16
    "Alley-Oop Finisher",       # 17
    "Break Starter",            # 18
    "One Man Fast Break",       # 19
    "Pick Pocket",              # 20
    "Active Hands",             # 21
    "Interceptor",              # 22
    "Eraser",                   # 23
    "Chase Down Artist",        # 24
    "Charge Card",              # 25
    "Rim Protector",            # 26
    "Brick Wall",               # 27
    "Bruiser",                  # 28
    "Pick Dodger",              # 29
    "Tenacious Rebounder",      # 30
    "Hustle Points",            # 31
    "Scrapper",                 # 32
    "Chase Down Block",         # 33 — some lists overlap with 24
    "Duality",                  # 34
    "Post Proficiency",         # 35
    "Spin Technician",          # 36
    "Drop Stepper",             # 37
    "Dream Shake",              # 38
    "Anti-Freeze",              # 39
    "Closer",                   # 40
    # Stubs 41–44 (unused but valid in the binary)
    "Assist Bonus",             # 41
    "Off Awareness Bonus",      # 42
    "Def Awareness Bonus",      # 43
    "Attribute Penalty",        # 44
]

# ─────────────────────────────────────────────────────────────────────────────
# Boundary records — 19 records where EVEN+ODD share TeamID byte
# ─────────────────────────────────────────────────────────────────────────────

BOUNDARY_RECORD_INDICES = [
    31, 63, 95, 127, 159, 191, 223, 255,
    287, 319, 351, 383, 415, 447, 479, 511,
    543, 575, 607,
]


# ═════════════════════════════════════════════════════════════════════════════
# CODECS
# ═════════════════════════════════════════════════════════════════════════════

def skill_decode(raw: int) -> int:
    """Decode a raw skill byte to a rating (25–110+).

    Formula: floor(raw / 3) + 25
    """
    return (raw // 3) + 25


def skill_encode(rating: int) -> int:
    """Encode a skill rating (25–110) to a raw byte value.

    Formula: (rating - 25) * 3
    Clamped to [0, 255] for safety.
    """
    raw = (rating - 25) * 3
    return max(0, min(SKILL_RAW_MAX, raw))


def skill_tier(raw: int) -> int:
    """Extract the discrete tier (0–13+) from a raw skill byte.

    Same as decode but without the +25 base.
    """
    return raw // 3


def tend_decode(raw: int) -> int:
    """Decode a raw tendency byte (passthrough with bounds check)."""
    return max(TENDENCY_MIN, min(TENDENCY_MAX, raw))


def tend_encode(value: int) -> int:
    """Encode a tendency value (passthrough with bounds check)."""
    return max(TENDENCY_MIN, min(TENDENCY_MAX, value))


# ═════════════════════════════════════════════════════════════════════════════
# HOT ZONE CODEC
# ═════════════════════════════════════════════════════════════════════════════

def hz_unpack(data: bytes) -> list[int]:
    """Unpack 14 hot zone values from 4 bytes (2 bits each, MSB-first).

    Returns list of 14 ints, each 0–3.
    """
    if len(data) < HOT_ZONE_BYTES:
        raise ValueError(f"Hot zone data too short: {len(data)} < {HOT_ZONE_BYTES}")

    # Combine 4 bytes into a 32-bit integer (big-endian)
    packed = struct.unpack(">I", data[:4])[0]
    zones = []
    for i in range(NUM_HOT_ZONES):
        # Extract 2-bit value, MSB-first (zone 0 is bits 31–30)
        shift = 30 - (i * 2)
        zones.append((packed >> shift) & 0x03)
    return zones


def hz_pack(zones: list[int]) -> bytes:
    """Pack 14 hot zone values (0–3 each) into 4 bytes, MSB-first."""
    if len(zones) != NUM_HOT_ZONES:
        raise ValueError(f"Expected {NUM_HOT_ZONES} zones, got {len(zones)}")

    packed = 0
    for i, val in enumerate(zones):
        if not (0 <= val <= 3):
            raise ValueError(f"Hot zone {i} value {val} out of range 0–3")
        shift = 30 - (i * 2)
        packed |= (val & 0x03) << shift
    return struct.pack(">I", packed)


# ═════════════════════════════════════════════════════════════════════════════
# CRC
# ═════════════════════════════════════════════════════════════════════════════

def compute_crc(data: bytes | bytearray) -> int:
    """Compute the .ROS CRC: zlib.crc32(data[4:]) & 0xFFFFFFFF."""
    return zlib.crc32(data[CRC_DATA_START:]) & 0xFFFFFFFF


def read_stored_crc(data: bytes | bytearray) -> int:
    """Read the CRC stored at offset 0x0000 (Big-Endian uint32)."""
    return struct.unpack(">I", data[CRC_OFFSET:CRC_OFFSET + 4])[0]


def validate_crc(data: bytes | bytearray) -> bool:
    """Return True if stored CRC matches computed CRC."""
    return read_stored_crc(data) == compute_crc(data)


def write_crc(data: bytearray) -> None:
    """Recalculate and write the CRC at offset 0x0000 (Big-Endian uint32)."""
    crc = compute_crc(data)
    struct.pack_into(">I", data, CRC_OFFSET, crc)


# ═════════════════════════════════════════════════════════════════════════════
# OFFSET CALCULATORS
# ═════════════════════════════════════════════════════════════════════════════

def player_data_offset(record_idx: int, sub_idx: int) -> int:
    """Calculate the absolute byte offset for a player's data block.

    Args:
        record_idx: Record index (0–831)
        sub_idx: 0 for EVEN player, 1 for ODD player

    Returns:
        Absolute byte offset into the .ROS buffer.
    """
    if not (0 <= record_idx < NUM_RECORDS):
        raise ValueError(f"record_idx {record_idx} out of range 0–{NUM_RECORDS - 1}")
    if sub_idx not in (0, 1):
        raise ValueError(f"sub_idx must be 0 (EVEN) or 1 (ODD), got {sub_idx}")

    record_start = ROSTER_DATA_START + (record_idx * RECORD_SIZE)

    if sub_idx == 0:
        return record_start  # EVEN — standard layout
    else:
        return record_start + ODD_NIBBLE_SHIFT  # ODD — nibble-shifted


def skill_byte_offset(record_idx: int, sub_idx: int, skill_idx: int) -> int:
    """Absolute byte offset of a specific skill field."""
    if not (0 <= skill_idx < NUM_SKILLS):
        raise ValueError(f"skill_idx {skill_idx} out of range 0–{NUM_SKILLS - 1}")
    base = player_data_offset(record_idx, sub_idx)
    return base + SKILL_OFFSET + skill_idx


def tendency_byte_offset(record_idx: int, sub_idx: int, tend_idx: int) -> int:
    """Absolute byte offset of a specific tendency field."""
    if not (0 <= tend_idx < NUM_TENDENCIES_TOTAL):
        raise ValueError(f"tend_idx {tend_idx} out of range 0–{NUM_TENDENCIES_TOTAL - 1}")
    base = player_data_offset(record_idx, sub_idx)
    return base + TENDENCY_OFFSET + tend_idx


def hot_zone_byte_offset(record_idx: int, sub_idx: int) -> int:
    """Absolute byte offset of the hot zone block (4 bytes)."""
    base = player_data_offset(record_idx, sub_idx)
    return base + HOT_ZONE_OFFSET


def sig_skill_byte_offset(record_idx: int, sub_idx: int, slot_idx: int) -> int:
    """Absolute byte offset of a signature skill slot."""
    if not (0 <= slot_idx < NUM_SIG_SLOTS):
        raise ValueError(f"slot_idx {slot_idx} out of range 0–{NUM_SIG_SLOTS - 1}")
    base = player_data_offset(record_idx, sub_idx)
    return base + SIG_SKILL_OFFSET + slot_idx


def is_boundary_record(record_idx: int) -> bool:
    """Check if a record is a boundary record (EVEN+ODD share TeamID)."""
    return record_idx in BOUNDARY_RECORD_INDICES


# ═════════════════════════════════════════════════════════════════════════════
# PHYSICAL MEASUREMENT HELPERS
# ═════════════════════════════════════════════════════════════════════════════

def read_height(data: bytes | bytearray, record_idx: int, sub_idx: int) -> float:
    """Read height (Float32 Big-Endian) in inches."""
    off = player_data_offset(record_idx, sub_idx) + OFF_HEIGHT
    return struct.unpack(">f", data[off:off + 4])[0]


def read_weight(data: bytes | bytearray, record_idx: int, sub_idx: int) -> float:
    """Read weight (Float32 Big-Endian) in lbs."""
    off = player_data_offset(record_idx, sub_idx) + OFF_WEIGHT
    return struct.unpack(">f", data[off:off + 4])[0]


def read_team_id(data: bytes | bytearray, record_idx: int, sub_idx: int) -> int:
    """Read TeamID (single byte)."""
    off = player_data_offset(record_idx, sub_idx) + OFF_TEAM_ID
    return data[off]

FIELD_TO_IDX = {
    "TIso": ("tendency", 43),
    "TPNR": ("tendency", 47),
    "TPNRRoll": ("tendency", 45),
    "TPost": ("tendency", 30),
    "TSpotUp": ("tendency", 46),
    "THandoff": ("tendency", 39),
    "TCut": ("tendency", 28),
    "TOffScreen": ("tendency", 16),
    "TTransition": ("tendency", 20),
    "TPutback": ("tendency", 27),
    "SSht3PT": ("skill", 3),
    "SShtMR": ("skill", 2),
    "SShtClose": ("skill", 1),
    "SShtFT": ("skill", 4),
    "SDribble": ("skill", 13),
    "SPass": ("skill", 14),
}

for _i in range(1, 15):
    FIELD_TO_IDX[f"hz_{_i}"] = ("hot_zone", _i - 1)
