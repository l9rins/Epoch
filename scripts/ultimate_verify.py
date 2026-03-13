import shutil
import os
from pathlib import Path
import json
import random

def deep_clean():
    data_dir = Path("data")
    if data_dir.exists():
        # Keep roster.ros if it exists
        roster_path = data_dir / "roster.ros"
        roster_data = None
        if roster_path.exists():
            roster_data = roster_path.read_bytes()
            
        shutil.rmtree(data_dir)
        print("Scorched earth cleanup of data/ directory complete.")
        
        data_dir.mkdir(parents=True, exist_ok=True)
        if roster_data:
            roster_path.write_bytes(roster_data)
            print("Restored roster.ros from memory.")
    
    for d in ["data/models", "data/journal", "data/synthetic", "data/predictions"]:
        Path(d).mkdir(parents=True, exist_ok=True)

def generate_synthetic_games(count=4000):
    path = Path("data/synthetic/games_10k.jsonl")
    with open(path, "w") as f:
        for i in range(count):
            game_id = f"G_{i}"
            states = []
            home_score = 0
            away_score = 0
            # Predetermine winner with a sharper strength bias
            home_strength = random.uniform(0.7, 1.3)
            away_strength = random.uniform(0.7, 1.3)
            for t in range(480, 0, -10): # 48 mins, 10s steps
                home_score += random.choices([0, 1, 2, 3], weights=[3, 1.5*home_strength, 1.5*home_strength, home_strength])[0]
                away_score += random.choices([0, 1, 2, 3], weights=[3, 1.5*away_strength, 1.5*away_strength, away_strength])[0]
                momentum = (home_score - away_score) / max(home_score + away_score, 1) * 50
                s = {
                    "time_remaining": t,
                    "clock": t,
                    "quarter": 1 + (480 - t) // 120,
                    "home_score": home_score,
                    "away_score": away_score,
                    "possession": random.randint(0, 1),
                    "momentum": momentum + random.uniform(-3, 3),
                    "pts_scored_this_poss": random.choice([0, 0, 0, 2, 3]),
                    "defensive_spacing": 50.0 + random.uniform(-15, 15),
                    "paint_density": 5.0 + random.uniform(-3, 3),
                    "three_point_coverage": 50.0 + random.uniform(-15, 15),
                    "pick_roll": random.randint(0, 1),
                    "fast_break": random.randint(0, 1),
                    "open_shooter": random.randint(0, 1),
                    "fatigue_home": max(0.75, 1.0 - (480 - t) / 4000),
                    "fatigue_away": max(0.75, 1.0 - (480 - t) / 4000)
                }
                states.append(s)
            
            f.write(json.dumps({
                "game_id": game_id, 
                "states": states,
                "final_home": home_score,
                "final_away": away_score
            }) + "\n")
    print(f"Generated {count} synthetic games.")

if __name__ == "__main__":
    deep_clean()
    generate_synthetic_games(500)
