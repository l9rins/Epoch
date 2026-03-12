"""
System B: Full 30-Team Attribute Pipeline
Fetches rosters for all 30 NBA teams, translates attributes, 
and generates individual .ROS POC files.
"""
import json
import shutil
import time
import sys
from pathlib import Path
from nba_api.stats.static import teams as nba_teams_static

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.pipeline.ingest.nba_api_client import NBAApiClient
from src.intelligence.translation_matrix import TranslationMatrix
from src.binary.constants import FIELD_TO_IDX

# For test compatibility and league reference
all_teams_static = nba_teams_static.get_teams()
NBA_TEAMS = [t["abbreviation"] for t in all_teams_static]

try:
    from tqdm import tqdm
except ImportError:
    def tqdm(iterable, **kwargs):
        return iterable

class FullLeaguePipeline:
    def __init__(self, season="2024-25"):
        self.season = season
        self.api_client = NBAApiClient()
        self.matrix = TranslationMatrix()
        self.data_dir = Path("data")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.base_ros = self.data_dir / "roster.ros"

    def find_player_in_ros(self, players, name):
        search_parts = [part for part in name.split() if part.lower() not in ("ii", "iii", "jr.", "sr.")]
        search = search_parts[-1].lower() if search_parts else ""
        for p in players:
            if search in p.name.lower():
                return p
        return None

    def write_field(self, data, record_index, sub_idx, field_name, value):
        if field_name not in FIELD_TO_IDX:
            return
        t, idx = FIELD_TO_IDX[field_name]
        if t == "tendency":
            write_tendency(data, record_index, sub_idx, idx, value, auto_crc=True)
        elif t == "skill":
            rating = (value * 3) + 25
            write_skill(data, record_index, sub_idx, idx, rating, auto_crc=True)
        elif t == "hot_zone":
            write_hot_zone(data, record_index, sub_idx, idx, value, auto_crc=True)

    def run(self):
        # Run contextual data seeders before roster pipeline
        print("Seeding calibration history...")
        try:
            from src.pipeline.calibration_seeder import seed_calibration_history
            seed_calibration_history()
        except Exception as e:
            print(f"Calibration seeder warning: {e}")

        print("Building fatigue context...")
        try:
            from src.pipeline.fatigue_seeder import run_fatigue_seeder
            run_fatigue_seeder()
        except Exception as e:
            print(f"Fatigue seeder warning: {e}")

        print("Assigning referee crews...")
        try:
            from src.pipeline.referee_seeder import run_referee_seeder
            run_referee_seeder()
        except Exception as e:
            print(f"Referee seeder warning: {e}")

        if not self.base_ros.exists():
            print(f"Error: {self.base_ros} not found. Ensure root roster exists.")
            return

        all_teams = nba_teams_static.get_teams()
        report = {
            "teams_complete": 0,
            "players_found": 0,
            "players_skipped": 0,
            "teams": []
        }

        print(f"Starting Full Pipeline for {len(all_teams)} teams...")

        for team in tqdm(all_teams, desc="Processing Teams"):
            abbr = team["abbreviation"]
            
            # 1. Fetch Roster
            try:
                roster = self.api_client.get_team_roster(abbr, self.season)
            except Exception as e:
                print(f"Error fetching roster for {abbr}: {e}")
                continue

            # 2. Save Roster JSON
            roster_json_path = self.data_dir / f"{abbr.lower()}_roster.json"
            with open(roster_json_path, "w") as f:
                json.dump(roster, f, indent=2)

            # 3. Copy base .ROS
            team_ros_path = self.data_dir / f"{abbr.lower()}_poc.ros"
            shutil.copy(self.base_ros, team_ros_path)

            # 4. Process Players
            ros_data = load_ros(team_ros_path)
            name_pool = build_name_pool(ros_data)
            ros_players = read_all_players(ros_data, name_pool)

            team_found = 0
            team_skipped = 0

            for player_name, player_id in roster.items():
                ros_p = self.find_player_in_ros(ros_players, player_name)
                if not ros_p:
                    team_skipped += 1
                    report["players_skipped"] += 1
                    continue

                try:
                    p_data = self.api_client.get_player_data(player_id, player_name, self.season)
                    ros_values = self.matrix.translate_player(p_data)

                    for field_name, tier_value in ros_values.items():
                        if "_" not in field_name or field_name.startswith("hz_"):
                            self.write_field(ros_data, ros_p.record_idx, ros_p.sub_idx, field_name, tier_value)
                    
                    team_found += 1
                    report["players_found"] += 1
                except Exception:
                    team_skipped += 1
                    report["players_skipped"] += 1
                
                # Tiny sleep to avoid API rate limiting
                time.sleep(0.5)

            # Save the team-specific .ROS
            save_ros(ros_data, str(team_ros_path))
            
            report["teams"].append({"abbr": abbr, "found": team_found, "skipped": team_skipped})
            report["teams_complete"] += 1

        # 5. Save Report
        with open(self.data_dir / "pipeline_report.json", "w") as f:
            json.dump(report, f, indent=2)
        
        print("\nPipeline Complete.")
        return report

if __name__ == "__main__":
    pipeline = FullLeaguePipeline()
    pipeline.run()
