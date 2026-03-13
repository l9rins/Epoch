"""
Tests — src/simulation/roster_hot_swap.py
SESSION B: Mid-Game Injury Hot-Swap

Tests are fully isolated — all binary operations use in-memory bytearrays,
never touching data/roster.ros.
"""
from __future__ import annotations

import pytest
import struct
import zlib
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# Fixtures — minimal valid .ROS-like bytearray for testing
# ---------------------------------------------------------------------------

def _make_minimal_ros(size: int = 8192) -> bytearray:
    """Create a minimal bytearray that passes CRC validation."""
    data = bytearray(size)
    # Write a valid CRC at offset 0
    crc = zlib.crc32(bytes(data[4:])) & 0xFFFFFFFF
    struct.pack_into(">I", data, 0, crc)
    return data


# ---------------------------------------------------------------------------
# CRC helpers
# ---------------------------------------------------------------------------

class TestCrcAfterHotSwap:
    """Every write must produce a valid CRC — this is the core invariant."""

    def test_zero_player_minutes_produces_valid_crc(self):
        from src.simulation.roster_hot_swap import zero_player_minutes
        from src.binary.constants import validate_crc
        data = _make_minimal_ros()
        result_data = zero_player_minutes(data, record_idx=0, sub_idx=0)
        assert validate_crc(result_data), "CRC invalid after zero_player_minutes"

    def test_boost_backup_produces_valid_crc(self):
        from src.simulation.roster_hot_swap import boost_backup_player
        from src.binary.constants import validate_crc
        data = _make_minimal_ros()
        result_data = boost_backup_player(data, record_idx=1, sub_idx=0)
        assert validate_crc(result_data), "CRC invalid after boost_backup_player"

    def test_execute_hot_swap_produces_valid_crc(self):
        from src.simulation.roster_hot_swap import execute_hot_swap
        data = _make_minimal_ros()
        result = execute_hot_swap(data, 0, 0, 1, 0)
        assert result["crc_valid"] is True


# ---------------------------------------------------------------------------
# zero_player_minutes
# ---------------------------------------------------------------------------

class TestZeroPlayerMinutes:
    def test_returns_bytearray(self):
        from src.simulation.roster_hot_swap import zero_player_minutes
        data = _make_minimal_ros()
        result = zero_player_minutes(data, 0, 0)
        assert isinstance(result, bytearray)

    def test_stamina_zeroed(self):
        from src.simulation.roster_hot_swap import zero_player_minutes
        from src.binary.constants import skill_byte_offset
        from src.simulation.roster_hot_swap import STAMINA_SKILL_INDEX
        data = _make_minimal_ros()
        # Pre-set stamina to non-zero
        off = skill_byte_offset(0, 0, STAMINA_SKILL_INDEX)
        data[off] = 99
        zero_player_minutes(data, 0, 0)
        assert data[off] == 0

    def test_durability_zeroed(self):
        from src.simulation.roster_hot_swap import zero_player_minutes
        from src.binary.constants import skill_byte_offset
        from src.simulation.roster_hot_swap import DURABILITY_SKILL_INDEX
        data = _make_minimal_ros()
        off = skill_byte_offset(0, 0, DURABILITY_SKILL_INDEX)
        data[off] = 85
        zero_player_minutes(data, 0, 0)
        assert data[off] == 0

    def test_modifies_in_place(self):
        from src.simulation.roster_hot_swap import zero_player_minutes
        data = _make_minimal_ros()
        original_id = id(data)
        result = zero_player_minutes(data, 0, 0)
        assert id(result) == original_id


# ---------------------------------------------------------------------------
# boost_backup_player
# ---------------------------------------------------------------------------

class TestBoostBackupPlayer:
    def test_stamina_increases(self):
        from src.simulation.roster_hot_swap import boost_backup_player
        from src.binary.constants import skill_byte_offset
        from src.simulation.roster_hot_swap import STAMINA_SKILL_INDEX, BACKUP_BOOST_AMOUNT
        data = _make_minimal_ros()
        off = skill_byte_offset(1, 0, STAMINA_SKILL_INDEX)
        data[off] = 50
        boost_backup_player(data, 1, 0)
        assert data[off] == 50 + BACKUP_BOOST_AMOUNT

    def test_boost_caps_at_255(self):
        from src.simulation.roster_hot_swap import boost_backup_player
        from src.binary.constants import skill_byte_offset, SKILL_RAW_MAX
        from src.simulation.roster_hot_swap import STAMINA_SKILL_INDEX
        data = _make_minimal_ros()
        off = skill_byte_offset(1, 0, STAMINA_SKILL_INDEX)
        data[off] = 253  # near max
        boost_backup_player(data, 1, 0)
        assert data[off] <= SKILL_RAW_MAX

    def test_returns_bytearray(self):
        from src.simulation.roster_hot_swap import boost_backup_player
        data = _make_minimal_ros()
        result = boost_backup_player(data, 1, 0)
        assert isinstance(result, bytearray)


# ---------------------------------------------------------------------------
# execute_hot_swap
# ---------------------------------------------------------------------------

class TestExecuteHotSwap:
    def test_success_true_when_crc_valid(self):
        from src.simulation.roster_hot_swap import execute_hot_swap
        data = _make_minimal_ros()
        result = execute_hot_swap(data, 0, 0, 1, 0)
        assert result["success"] is True

    def test_result_has_required_keys(self):
        from src.simulation.roster_hot_swap import execute_hot_swap
        data = _make_minimal_ros()
        result = execute_hot_swap(data, 0, 0, 1, 0)
        required = {"success", "crc_valid", "injured", "backup", "swap_ts"}
        assert required.issubset(set(result.keys()))

    def test_injured_indices_in_result(self):
        from src.simulation.roster_hot_swap import execute_hot_swap
        data = _make_minimal_ros()
        result = execute_hot_swap(data, 5, 1, 6, 0)
        assert result["injured"]["record_idx"] == 5
        assert result["injured"]["sub_idx"] == 1

    def test_backup_indices_in_result(self):
        from src.simulation.roster_hot_swap import execute_hot_swap
        data = _make_minimal_ros()
        result = execute_hot_swap(data, 5, 1, 6, 0)
        assert result["backup"]["record_idx"] == 6
        assert result["backup"]["sub_idx"] == 0

    def test_swap_ts_is_recent(self):
        import time
        from src.simulation.roster_hot_swap import execute_hot_swap
        data = _make_minimal_ros()
        result = execute_hot_swap(data, 0, 0, 1, 0)
        assert abs(result["swap_ts"] - time.time()) < 2.0


# ---------------------------------------------------------------------------
# Tendency write guard — ENGINE INTERNAL indices 57-68 must never be written
# ---------------------------------------------------------------------------

class TestTendencyWriteGuard:
    def test_writing_to_index_57_raises(self):
        from src.simulation.roster_hot_swap import _write_tendency_safe
        data = _make_minimal_ros()
        with pytest.raises(ValueError, match="ENGINE INTERNAL"):
            _write_tendency_safe(data, 0, 0, tend_idx=57, value=50)

    def test_writing_to_index_68_raises(self):
        from src.simulation.roster_hot_swap import _write_tendency_safe
        data = _make_minimal_ros()
        with pytest.raises(ValueError, match="ENGINE INTERNAL"):
            _write_tendency_safe(data, 0, 0, tend_idx=68, value=50)

    def test_writing_to_index_56_ok(self):
        from src.simulation.roster_hot_swap import _write_tendency_safe
        from src.binary.constants import validate_crc
        data = _make_minimal_ros(size=16384)
        # Should not raise — index 56 is the last writable tendency
        _write_tendency_safe(data, 0, 0, tend_idx=56, value=50)


# ---------------------------------------------------------------------------
# build_post_swap_game_state
# ---------------------------------------------------------------------------

class TestBuildPostSwapGameState:
    def test_home_offense_reduced_when_home_injured(self):
        from src.simulation.roster_hot_swap import build_post_swap_game_state
        pre = {"home_offense": 110.0, "home_defense": 108.0,
               "away_offense": 106.0, "away_defense": 106.0,
               "injured_team": "home"}
        post = build_post_swap_game_state(pre)
        assert post["home_offense"] < pre["home_offense"]

    def test_away_offense_reduced_when_away_injured(self):
        from src.simulation.roster_hot_swap import build_post_swap_game_state
        pre = {"home_offense": 110.0, "home_defense": 108.0,
               "away_offense": 106.0, "away_defense": 106.0,
               "injured_team": "away"}
        post = build_post_swap_game_state(pre)
        assert post["away_offense"] < pre["away_offense"]

    def test_pre_swap_not_mutated(self):
        from src.simulation.roster_hot_swap import build_post_swap_game_state
        pre = {"home_offense": 110.0, "home_defense": 108.0,
               "away_offense": 106.0, "away_defense": 106.0,
               "injured_team": "home"}
        original_offense = pre["home_offense"]
        build_post_swap_game_state(pre)
        assert pre["home_offense"] == original_offense


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

class TestConstants:
    def test_minutes_zeroed_value_is_zero(self):
        from src.simulation.roster_hot_swap import MINUTES_ZEROED_VALUE
        assert MINUTES_ZEROED_VALUE == 0

    def test_backup_boost_amount_positive(self):
        from src.simulation.roster_hot_swap import BACKUP_BOOST_AMOUNT
        assert BACKUP_BOOST_AMOUNT > 0

    def test_stamina_skill_index(self):
        from src.simulation.roster_hot_swap import STAMINA_SKILL_INDEX
        assert STAMINA_SKILL_INDEX == 30
