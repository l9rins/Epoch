"""
Epoch Engine — Binary Engine Test Suite

Tests for CRC, skill codec, tendency codec, nibble-shift offsets,
hot zone pack/unpack, and boundary record safety.

Run: python -m pytest tests/ -v
"""

import struct
import zlib
from pathlib import Path

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

# Adjust import path — tests run from project root
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from binary.constants import (
    BOUNDARY_RECORD_INDICES,
    CRC_DATA_START,
    CRC_OFFSET,
    HOT_ZONE_BYTES,
    NUM_HOT_ZONES,
    NUM_RECORDS,
    NUM_SIG_SLOTS,
    NUM_SKILLS,
    NUM_TENDENCIES,
    NUM_TENDENCIES_TOTAL,
    ODD_NIBBLE_SHIFT,
    RECORD_SIZE,
    ROSTER_DATA_START,
    SKILL_MAX_TIER,
    SKILL_MIN_TIER,
    SKILL_RAW_MAX,
    TENDENCY_MAX,
    TENDENCY_MIN,
    compute_crc,
    hot_zone_byte_offset,
    hz_pack,
    hz_unpack,
    is_boundary_record,
    player_data_offset,
    read_stored_crc,
    skill_byte_offset,
    skill_decode,
    skill_encode,
    skill_tier,
    tend_decode,
    tend_encode,
    tendency_byte_offset,
    validate_crc,
    write_crc,
)
from binary.ros_reader import Player, RosCorruptionError, check_crc, read_player
from binary.ros_writer import (
    BoundaryRecordError,
    recalculate_crc,
    write_hot_zone,
    write_hot_zones,
    write_player,
    write_skill,
    write_team_id,
    write_tendency,
)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def make_synthetic_ros(size: int = 3_000_000) -> bytearray:
    """Create a synthetic .ROS buffer with valid CRC.

    Fill with 0xFF (so skill bytes decode to valid high values)
    then write a correct CRC.
    """
    data = bytearray(b'\x00' * size)
    write_crc(data)
    return data


def make_ros_with_player_data(record_idx: int = 0, sub_idx: int = 0) -> bytearray:
    """Create a synthetic .ROS buffer with specific player data for testing."""
    data = make_synthetic_ros()

    # Write some recognizable skill values
    for i in range(NUM_SKILLS):
        off = skill_byte_offset(record_idx, sub_idx, i)
        # Encode a rating of 25 + i (valid range)
        data[off] = skill_encode(25 + min(i, 85))

    # Write some tendency values
    for i in range(NUM_TENDENCIES):
        off = tendency_byte_offset(record_idx, sub_idx, i)
        data[off] = min(i * 2, TENDENCY_MAX)

    # Write neutral hot zones
    hz_off = hot_zone_byte_offset(record_idx, sub_idx)
    packed = hz_pack([1] * NUM_HOT_ZONES)  # All neutral
    data[hz_off:hz_off + HOT_ZONE_BYTES] = packed

    # Fix CRC
    write_crc(data)
    return data


# ═════════════════════════════════════════════════════════════════════════════
# CRC TESTS
# ═════════════════════════════════════════════════════════════════════════════

class TestCRC:
    """CRC compute → store → validate round-trip tests."""

    def test_crc_round_trip(self):
        """Compute CRC, store it, then validate — must match."""
        data = bytearray(b'\x00' * 1000)
        write_crc(data)
        assert validate_crc(data)

    def test_crc_detects_corruption(self):
        """Modify a byte after CRC write — validation must fail."""
        data = bytearray(b'\x00' * 1000)
        write_crc(data)
        # Corrupt a byte in the data region
        data[100] = 0xFF
        assert not validate_crc(data)

    def test_crc_stored_big_endian(self):
        """CRC must be stored as Big-Endian uint32 at offset 0."""
        data = bytearray(b'\x00' * 1000)
        write_crc(data)
        stored = struct.unpack(">I", data[0:4])[0]
        computed = zlib.crc32(data[4:]) & 0xFFFFFFFF
        assert stored == computed

    def test_crc_empty_data_region(self):
        """CRC of all-zeros (after the header) should be deterministic."""
        data1 = bytearray(b'\x00' * 500)
        data2 = bytearray(b'\x00' * 500)
        write_crc(data1)
        write_crc(data2)
        assert data1[:4] == data2[:4]

    def test_crc_different_data_different_crc(self):
        """Different data must produce different CRC."""
        data1 = bytearray(b'\x00' * 500)
        data2 = bytearray(b'\x01' * 500)
        write_crc(data1)
        write_crc(data2)
        assert data1[:4] != data2[:4]

    @given(payload=st.binary(min_size=100, max_size=5000))
    @settings(max_examples=50)
    def test_crc_round_trip_hypothesis(self, payload):
        """Property test: any payload → write CRC → validate → True."""
        data = bytearray(b'\x00\x00\x00\x00' + payload)
        write_crc(data)
        assert validate_crc(data)

    def test_recalculate_crc_returns_value(self):
        """recalculate_crc should return the new CRC value."""
        data = make_synthetic_ros()
        crc = recalculate_crc(data)
        assert crc == read_stored_crc(data)


# ═════════════════════════════════════════════════════════════════════════════
# SKILL CODEC TESTS
# ═════════════════════════════════════════════════════════════════════════════

class TestSkillCodec:
    """Skill encode/decode round-trip and boundary tests."""

    def test_decode_basic(self):
        """floor(0/3)+25 = 25, floor(39/3)+25 = 38."""
        assert skill_decode(0) == 25
        assert skill_decode(3) == 26
        assert skill_decode(39) == 38

    def test_encode_basic(self):
        """(25-25)*3 = 0, (26-25)*3 = 3."""
        assert skill_encode(25) == 0
        assert skill_encode(26) == 3

    def test_round_trip_exact(self):
        """For encoded values, encode(decode(x)) should produce a value
        that decodes back to the same rating."""
        for rating in range(25, 65):  # Standard tier range
            raw = skill_encode(rating)
            decoded = skill_decode(raw)
            assert decoded == rating

    @given(raw=st.integers(min_value=0, max_value=255))
    @settings(max_examples=100)
    def test_decode_always_valid(self, raw):
        """Property: decode always returns >= 25."""
        result = skill_decode(raw)
        assert result >= 25

    @given(rating=st.integers(min_value=25, max_value=110))
    @settings(max_examples=100)
    def test_encode_clamped(self, rating):
        """Property: encode always returns 0–255."""
        raw = skill_encode(rating)
        assert 0 <= raw <= SKILL_RAW_MAX

    def test_tier_extraction(self):
        """Tier should be floor(raw/3)."""
        assert skill_tier(0) == 0
        assert skill_tier(3) == 1
        assert skill_tier(39) == 13

    def test_encode_clamp_low(self):
        """Encoding rating < 25 should clamp to 0."""
        assert skill_encode(20) == 0  # (20-25)*3 = -15 → clamped to 0

    def test_modded_high_rating(self):
        """Support modded ratings up to 110 (cap at 255)."""
        raw = skill_encode(110)
        assert raw == 255
        assert skill_decode(255) == 110  # floor(255/3)+25 = 85+25 = 110


# ═════════════════════════════════════════════════════════════════════════════
# TENDENCY CODEC TESTS
# ═════════════════════════════════════════════════════════════════════════════

class TestTendencyCodec:
    """Tendency encode/decode with bounds check."""

    def test_passthrough(self):
        """Tendency codec is a passthrough — value in = value out."""
        for v in range(100):
            assert tend_encode(v) == min(v, TENDENCY_MAX)
            assert tend_decode(v) == min(v, TENDENCY_MAX)

    def test_clamp_high(self):
        """Values above 99 are clamped."""
        assert tend_encode(150) == TENDENCY_MAX
        assert tend_decode(150) == TENDENCY_MAX

    def test_clamp_low(self):
        """Negative values are clamped to 0."""
        assert tend_encode(-5) == TENDENCY_MIN

    @given(val=st.integers(min_value=0, max_value=99))
    @settings(max_examples=50)
    def test_round_trip(self, val):
        """encode(decode(v)) == v for valid values."""
        assert tend_encode(tend_decode(val)) == val


# ═════════════════════════════════════════════════════════════════════════════
# NIBBLE-SHIFT / OFFSET TESTS
# ═════════════════════════════════════════════════════════════════════════════

class TestOffsets:
    """Verify EVEN vs ODD offset calculation and nibble shift."""

    def test_even_player_at_record_start(self):
        """EVEN player (sub_idx=0) starts at record start."""
        offset_even = player_data_offset(0, 0)
        assert offset_even == ROSTER_DATA_START

    def test_odd_player_shifted(self):
        """ODD player (sub_idx=1) is shifted by 0x1C7."""
        offset_even = player_data_offset(0, 0)
        offset_odd = player_data_offset(0, 1)
        assert offset_odd == offset_even + ODD_NIBBLE_SHIFT

    def test_consecutive_records(self):
        """Record N+1 starts RECORD_SIZE bytes after record N."""
        off_0 = player_data_offset(0, 0)
        off_1 = player_data_offset(1, 0)
        assert off_1 - off_0 == RECORD_SIZE

    def test_odd_stride_same_as_even(self):
        """ODD players in consecutive records should also be RECORD_SIZE apart."""
        off_0 = player_data_offset(0, 1)
        off_1 = player_data_offset(1, 1)
        assert off_1 - off_0 == RECORD_SIZE

    def test_even_odd_dont_overlap_skills(self):
        """EVEN and ODD skill ranges should not overlap within same record."""
        even_start = skill_byte_offset(0, 0, 0)
        even_end = skill_byte_offset(0, 0, NUM_SKILLS - 1)
        odd_start = skill_byte_offset(0, 1, 0)
        # ODD starts well past EVEN's end
        assert odd_start > even_end

    def test_record_idx_range_check(self):
        """Out-of-range record_idx should raise ValueError."""
        with pytest.raises(ValueError):
            player_data_offset(-1, 0)
        with pytest.raises(ValueError):
            player_data_offset(NUM_RECORDS, 0)

    def test_sub_idx_range_check(self):
        """Out-of-range sub_idx should raise ValueError."""
        with pytest.raises(ValueError):
            player_data_offset(0, 2)

    def test_last_record_offset(self):
        """Last record (831) should produce valid offsets."""
        off = player_data_offset(NUM_RECORDS - 1, 1)
        assert off > 0


# ═════════════════════════════════════════════════════════════════════════════
# HOT ZONE TESTS
# ═════════════════════════════════════════════════════════════════════════════

class TestHotZones:
    """Hot zone 2-bit pack/unpack round-trip tests."""

    def test_all_neutral(self):
        """14 neutral zones (value=1) should pack/unpack cleanly."""
        zones = [1] * NUM_HOT_ZONES
        packed = hz_pack(zones)
        assert len(packed) == HOT_ZONE_BYTES
        unpacked = hz_unpack(packed)
        assert unpacked == zones

    def test_all_cold(self):
        """14 cold zones (value=0) → all zero bits."""
        zones = [0] * NUM_HOT_ZONES
        packed = hz_pack(zones)
        unpacked = hz_unpack(packed)
        assert unpacked == zones

    def test_all_burned(self):
        """14 burned zones (value=3) → all 11 bits."""
        zones = [3] * NUM_HOT_ZONES
        packed = hz_pack(zones)
        unpacked = hz_unpack(packed)
        assert unpacked == zones

    def test_mixed_values(self):
        """Mixed hot zone values should round-trip correctly."""
        zones = [0, 1, 2, 3, 0, 1, 2, 3, 0, 1, 2, 3, 0, 1]
        packed = hz_pack(zones)
        unpacked = hz_unpack(packed)
        assert unpacked == zones

    def test_wrong_count_raises(self):
        """Packing != 14 zones should raise ValueError."""
        with pytest.raises(ValueError):
            hz_pack([1] * 13)
        with pytest.raises(ValueError):
            hz_pack([1] * 15)

    def test_out_of_range_value_raises(self):
        """Zone value > 3 should raise ValueError."""
        zones = [1] * 14
        zones[5] = 4
        with pytest.raises(ValueError):
            hz_pack(zones)

    @given(zones=st.lists(st.integers(min_value=0, max_value=3),
                          min_size=NUM_HOT_ZONES, max_size=NUM_HOT_ZONES))
    @settings(max_examples=100)
    def test_round_trip_hypothesis(self, zones):
        """Property: any valid zone list → pack → unpack → same list."""
        packed = hz_pack(zones)
        unpacked = hz_unpack(packed)
        assert unpacked == zones


# ═════════════════════════════════════════════════════════════════════════════
# BOUNDARY RECORD TESTS
# ═════════════════════════════════════════════════════════════════════════════

class TestBoundaryRecords:
    """Boundary record safety checks."""

    def test_known_boundary_records(self):
        """All 19 known boundary records should be flagged."""
        for idx in BOUNDARY_RECORD_INDICES:
            assert is_boundary_record(idx), f"Record {idx} should be boundary"

    def test_non_boundary_record(self):
        """Record 0 should not be a boundary record."""
        assert not is_boundary_record(0)

    def test_team_id_boundary_blocked(self):
        """Writing TeamID to a boundary record should raise BoundaryRecordError."""
        data = make_synthetic_ros()
        with pytest.raises(BoundaryRecordError):
            write_team_id(data, BOUNDARY_RECORD_INDICES[0], 0, 5)

    def test_team_id_boundary_forced(self):
        """Writing TeamID to boundary with force_boundary=True should work."""
        data = make_synthetic_ros()
        rec_idx = BOUNDARY_RECORD_INDICES[0]
        write_team_id(data, rec_idx, 0, 5, force_boundary=True)
        # Verify it wrote
        from binary.constants import read_team_id
        assert read_team_id(data, rec_idx, 0) == 5


# ═════════════════════════════════════════════════════════════════════════════
# READ/WRITE ROUND-TRIP TESTS
# ═════════════════════════════════════════════════════════════════════════════

class TestReadWriteRoundTrip:
    """Read → modify → write → read back → verify."""

    def test_skill_write_read_round_trip(self):
        """Write a skill rating, read it back, should match."""
        data = make_ros_with_player_data()
        write_skill(data, 0, 0, 0, 75)  # Write OVR = 75
        player = read_player(data, 0, 0)
        assert player.skills[0] == 75

    def test_tendency_write_read_round_trip(self):
        """Write a tendency, read it back, should match."""
        data = make_ros_with_player_data()
        write_tendency(data, 0, 0, 10, 55)
        player = read_player(data, 0, 0)
        assert player.tendencies[10] == 55

    def test_hot_zone_write_read_round_trip(self):
        """Write a hot zone, read it back, should match."""
        data = make_ros_with_player_data()
        write_hot_zone(data, 0, 0, 5, 3)  # Set zone 5 to BURNED
        player = read_player(data, 0, 0)
        assert player.hot_zones[5] == 3

    def test_bulk_hot_zones_round_trip(self):
        """Write all hot zones, read back, should match."""
        data = make_ros_with_player_data()
        zones = [0, 1, 2, 3, 0, 1, 2, 3, 0, 1, 2, 3, 0, 1]
        write_hot_zones(data, 0, 0, zones)
        player = read_player(data, 0, 0)
        assert player.hot_zones == zones

    def test_crc_valid_after_write(self):
        """CRC must be valid after any write operation."""
        data = make_ros_with_player_data()
        write_skill(data, 0, 0, 3, 99)
        assert validate_crc(data)

    def test_overall_i_blocked(self):
        """Writing to skill index 41 (Overall_I) should raise ValueError."""
        data = make_ros_with_player_data()
        with pytest.raises(ValueError, match="Overall_I"):
            write_skill(data, 0, 0, 41, 50)

    def test_internal_tendency_blocked(self):
        """Writing to tendency >= 57 should raise ValueError."""
        data = make_ros_with_player_data()
        with pytest.raises(ValueError, match="engine-internal"):
            write_tendency(data, 0, 0, 57, 10)

    def test_odd_player_write_read(self):
        """ODD player (sub_idx=1) write/read round-trip."""
        data = make_ros_with_player_data(record_idx=5, sub_idx=1)
        write_skill(data, 5, 1, 3, 88)
        player = read_player(data, 5, 1)
        assert player.skills[3] == 88

    def test_write_player_bulk(self):
        """Bulk write_player then read back all fields."""
        data = make_ros_with_player_data()
        player = read_player(data, 0, 0)

        # Modify various fields
        player.skills[0] = 90   # OVR
        player.skills[3] = 95   # 3PT
        player.tendencies[12] = 80  # Shot 3PT tendency
        player.hot_zones = [2, 2, 2, 1, 1, 1, 0, 0, 3, 3, 3, 1, 1, 2]

        write_player(data, player)

        # Read back
        p2 = read_player(data, 0, 0)
        assert p2.skills[0] == 90
        assert p2.skills[3] == 95
        assert p2.tendencies[12] == 80
        assert p2.hot_zones == [2, 2, 2, 1, 1, 1, 0, 0, 3, 3, 3, 1, 1, 2]
        assert validate_crc(data)


# ═════════════════════════════════════════════════════════════════════════════
# INTEGRATION TEST (requires actual .ROS file)
# ═════════════════════════════════════════════════════════════════════════════

ROS_FILE = Path(__file__).resolve().parent.parent / "data" / "roster.ros"


@pytest.mark.skipif(
    not ROS_FILE.exists(),
    reason=f"No .ROS file at {ROS_FILE} — drop roster.ros in data/ for integration tests"
)
class TestIntegration:
    """Integration tests against real .ROS file."""

    def test_load_and_validate_crc(self):
        """Load real .ROS file and validate CRC."""
        data = bytearray(ROS_FILE.read_bytes())
        assert validate_crc(data), "CRC validation failed on real .ROS file"

    def test_parse_all_players(self):
        """Parse all 1664 players without exceptions."""
        from binary.ros_reader import read_all_players
        data = bytearray(ROS_FILE.read_bytes())
        players = read_all_players(data)
        assert len(players) > 0, "No players parsed"
        # Every player should have valid skill count
        for p in players:
            assert len(p.skills) == NUM_SKILLS, (
                f"Player at record {p.record_idx} sub {p.sub_idx} has "
                f"{len(p.skills)} skills, expected {NUM_SKILLS}"
            )

    def test_all_skills_in_valid_range(self):
        """All decoded skills should be >= 25."""
        from binary.ros_reader import read_all_players
        data = bytearray(ROS_FILE.read_bytes())
        players = read_all_players(data)
        for p in players:
            for i, rating in enumerate(p.skills):
                assert rating >= 25, (
                    f"Player record={p.record_idx} sub={p.sub_idx} "
                    f"skill[{i}]={rating} < 25"
                )

    def test_modify_and_revalidate(self):
        """Read → modify one skill → write → CRC still valid."""
        data = bytearray(ROS_FILE.read_bytes())
        assert validate_crc(data)

        # Read first player's OVR
        player = read_player(data, 0, 0)
        original_ovr = player.skills[0]

        # Write new OVR
        new_ovr = 85 if original_ovr != 85 else 80
        write_skill(data, 0, 0, 0, new_ovr)

        # Verify CRC is still valid
        assert validate_crc(data)

        # Verify the write stuck
        player2 = read_player(data, 0, 0)
        assert player2.skills[0] == new_ovr
