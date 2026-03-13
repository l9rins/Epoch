import sys
from pathlib import Path
import subprocess

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from src.intelligence.translation_matrix import TranslationMatrix
from src.binary.ros_reader import load_ros, check_crc

class TestTranslationMatrix:
    def test_tendency_bounds(self):
        matrix = TranslationMatrix()
        for pt in matrix.synergy_map.keys():
            res_0 = matrix.translate_player({"synergy": {pt: {"poss_pct": 0.0}}})
            res_1 = matrix.translate_player({"synergy": {pt: {"poss_pct": 1.0}}})
            ros_field = matrix.synergy_map[pt]
            assert res_0[ros_field] == 0
            assert res_1[ros_field] == 99

    def test_skill_bounds(self):
        matrix = TranslationMatrix()
        for sht_key, ros_field in matrix.shooting_map.items():
            res_0 = matrix.translate_player({"shooting": {sht_key: 0.0}})
            res_1 = matrix.translate_player({"shooting": {sht_key: 1.0}})
            assert res_0[ros_field] == 0
            assert res_1[ros_field] == 13

    def test_hot_zone_bounds(self):
        matrix = TranslationMatrix()
        res = matrix.translate_player({"hot_zones": {"zone_1": 0.1, "zone_2": 0.9}})
        assert res["hz_1"] == 0
        assert res["hz_2"] == 1

    def test_curry_3pt_elite(self):
        from src.pipeline.ingest.nba_api_client import NBAApiClient
        client = NBAApiClient()
        curry_data = client.get_player_data(201939, "2024-25")
        matrix = TranslationMatrix()
        res = matrix.translate_player(curry_data)
        assert res["SSht3PT"] >= 11

    def test_curry_pnr_high(self):
        from src.pipeline.ingest.nba_api_client import NBAApiClient
        client = NBAApiClient()
        curry_data = client.get_player_data(201939, "2024-25")
        matrix = TranslationMatrix()
        res = matrix.translate_player(curry_data)
        assert res["TPNR"] >= 2

    def test_original_unchanged(self):
        script_path = Path(__file__).resolve().parent.parent / "scripts" / "curry_proof_of_concept.py"
        roster_path = Path(__file__).resolve().parent.parent / "data" / "roster.ros"
        if not roster_path.exists():
            pytest.skip("No roster.ros found — binary asset not in version control")
        before_bytes = roster_path.read_bytes()
        
        subprocess.run([sys.executable, str(script_path)], check=True)
        
        after_bytes = roster_path.read_bytes()
        assert before_bytes == after_bytes

    def test_crc_valid_after_write(self):
        poc_path = Path(__file__).resolve().parent.parent / "data" / "curry_poc.ros"
        if not poc_path.exists():
            pytest.skip("No curry_poc.ros found")
        data = load_ros(poc_path)
        assert check_crc(data)

    def test_warriors_roster_valid_crc(self):
        import json
        poc_path = Path(__file__).resolve().parent.parent / "data" / "warriors_poc.ros"
        if not poc_path.exists():
            pytest.skip("No warriors_poc.ros found")

        # CRC must be valid
        data = load_ros(poc_path)
        assert check_crc(data)

        # Verify players who WERE in 2K14 got written correctly
        # Only check veterans who existed in 2013-14
        from src.binary.ros_reader import build_name_pool, read_all_players
        name_pool = build_name_pool(data)
        players = read_all_players(data, name_pool)

        veterans = ["Curry", "Green"]  # known 2K14 players
        for last_name in veterans:
            found = next(
                (p for p in players if last_name.lower() == p.name.lower()),
                None
            )
            if found is None:
                pytest.skip(f"{last_name} not in this .ROS file")
            # Verify SSht3PT was written above default (skill index 3)
            assert found.skills[3] > 25, (
                f"{last_name} SSht3PT still at default 25 — write failed"
            )

    @given(val=st.floats(min_value=0.0, max_value=1.0))
    @settings(max_examples=50)
    def test_property_bounds(self, val):
        matrix = TranslationMatrix()
        res = matrix.translate_player({
            "synergy": {"Isolation": {"poss_pct": val}},
            "shooting": {"fg3_pct": val},
            "hot_zones": {"zone_1": val}
        })
        assert 0 <= res["TIso"] <= 99
        assert 0 <= res["SSht3PT"] <= 13
        assert res["hz_1"] in (0, 1)
