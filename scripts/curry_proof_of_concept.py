import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.pipeline.ingest.nba_api_client import NBAApiClient
from src.intelligence.translation_matrix import TranslationMatrix
from src.binary.ros_reader import load_ros, build_name_pool, read_all_players
from src.binary.ros_writer import write_skill, write_tendency, write_hot_zone, save_ros
from src.binary.constants import FIELD_TO_IDX

class ExtendedPlayer:
    def __init__(self, p):
        self.p = p
        self.record_index = p.record_idx
        self.sub_idx = p.sub_idx
    def __getattr__(self, name):
        if name in FIELD_TO_IDX:
            t, idx = FIELD_TO_IDX[name]
            if t == "tendency": return self.p.tendencies[idx]
            if t == "skill": return self.p.skills[idx]
            if t == "hot_zone": return self.p.hot_zones[idx]
        return getattr(self.p, name)

class RosReader:
    def __init__(self, path: str):
        self.path = path
        self.data = load_ros(path)
        self.name_pool = build_name_pool(self.data)
        self.players = read_all_players(self.data, self.name_pool)
        
    def find_player_by_name(self, name: str):
        search = name.split()[-1] # Match by last name
        for p in self.players:
            if search in p.name:
                return ExtendedPlayer(p)
        raise ValueError(f"Player {name} not found")

class RosWriter:
    def __init__(self, path: str):
        self.path = path
        self.data = load_ros(path)
    
    def write_field(self, record_index: int, sub_idx: int, field_name: str, value: int):
        if field_name not in FIELD_TO_IDX:
            return
        t, idx = FIELD_TO_IDX[field_name]
        if t == "tendency":
            write_tendency(self.data, record_index, sub_idx, idx, value, auto_crc=True)
        elif t == "skill":
            rating = (value * 3) + 25
            write_skill(self.data, record_index, sub_idx, idx, rating, auto_crc=True)
        elif t == "hot_zone":
            write_hot_zone(self.data, record_index, sub_idx, idx, value, auto_crc=True)
            
    def save(self):
        save_ros(self.data, self.path)

if __name__ == "__main__":
    # 1. Pull real data
    client = NBAApiClient()
    curry_data = client.get_player_data(201939, "2024-25")

    # 2. Translate to .ROS values
    matrix = TranslationMatrix()
    ros_values = matrix.translate_player(curry_data)

    # 3. Work on a COPY — never touch original
    shutil.copy("data/roster.ros", "data/curry_poc.ros")

    # 4. Read copy, find Curry, write new values
    reader = RosReader("data/curry_poc.ros")
    writer = RosWriter("data/curry_poc.ros")
    curry_record = reader.find_player_by_name("Stephen Curry")

    for field_name, tier_value in ros_values.items():
        if "_" not in field_name or field_name.startswith("hz_"):
            writer.write_field(curry_record.record_index, curry_record.sub_idx, field_name, tier_value)
            
    writer.save()

    # 5. Print before/after comparison
    print("\n=== CURRY TRANSLATION MATRIX RESULTS ===\n")
    print(f"{'FIELD':<20} {'BEFORE':>8} {'AFTER':>8} {'SOURCE':>12} {'CONFIDENCE':>12}")
    print("-" * 65)

    original = RosReader("data/roster.ros").find_player_by_name("Stephen Curry")
    updated  = RosReader("data/curry_poc.ros").find_player_by_name("Stephen Curry")

    key_fields = ["TIso", "TPNR", "TSpotUp", "TTransition", "SSht3PT",
                  "SShtMR", "SShtFT", "SDribble", "SPass"]

    for field in key_fields:
        before = getattr(original, field)
        after  = getattr(updated, field)
        conf   = ros_values.get(f"{field}_confidence", "MEDIUM")
        src    = ros_values.get(f"{field}_source", "nba_api")
        changed = "<--" if before != after else ""
        print(f"{field:<20} {before:>8} {after:>8} {src:>12} {conf:>10} {changed}")

    print(f"\nCurry POC file saved: data/curry_poc.ros")
    print("Load this file in NBA 2K14 and verify Curry plays differently.")
    print("Expected: more pick-and-roll, more spot-up shooting, less post-up.")
