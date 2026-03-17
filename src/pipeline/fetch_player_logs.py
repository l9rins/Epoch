import sys
import json
import time
from pathlib import Path
from nba_api.stats.endpoints import playergamelogs
import pandas as pd

def fetch_player_logs(seasons=["2023-24", "2024-25"]):
    all_logs = []
    output_path = Path("data/player_game_logs.jsonl")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Check for existing logs to resume
    existing_ids = set()
    if output_path.exists():
        with open(output_path, "r") as f:
            for line in f:
                log = json.loads(line)
                existing_ids.add(f"{log['player_id']}_{log['game_id']}")

    for season in seasons:
        print(f"Fetching logs for season: {season}")
        try:
            # Fetch all player logs for the season at once
            logs = playergamelogs.PlayerGameLogs(
                season_nullable=season,
                season_type_nullable='Regular Season'
            ).get_data_frames()[0]
            
            # Convert to our schema
            for _, row in logs.iterrows():
                key = f"{row['PLAYER_ID']}_{row['GAME_ID']}"
                if key in existing_ids:
                    continue
                    
                log_entry = {
                    "player_id": str(row['PLAYER_ID']),
                    "player_name": row['PLAYER_NAME'],
                    "game_id": row['GAME_ID'],
                    "game_date": row['GAME_DATE'][:10],
                    "season": season,
                    "team": row['TEAM_ABBREVIATION'],
                    "is_home": "vs." in row['MATCHUP'],
                    "minutes": float(row['MIN']),
                    "usage_rate": float(row.get('USG_PCT', 0.22)), # USG_PCT might be in some versions
                    "points": int(row['PTS']),
                    "rebounds": int(row['REB']),
                    "assists": int(row['AST']),
                }
                
                with open(output_path, "a") as f:
                    f.write(json.dumps(log_entry) + "\n")
                
                existing_ids.add(key)
                all_logs.append(log_entry)
                
            print(f"  Added {len(all_logs)} entries for {season}")
            time.sleep(2.2) # be nice to nba_api
            
        except Exception as e:
            print(f"Error fetching logs for {season}: {e}")
            
    return len(all_logs)

if __name__ == "__main__":
    count = fetch_player_logs()
    print(f"Total player logs fetched: {count}")
