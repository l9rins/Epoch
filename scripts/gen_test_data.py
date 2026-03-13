import json
import random
from pathlib import Path

def generate_synthetic_games(count=1000):
    path = Path("data/synthetic/games_10k.jsonl")
    path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(path, "w") as f:
        for i in range(count):
            game_id = f"G_{i}"
            states = []
            home_score = 0
            away_score = 0
            for t in range(480, 0, -10): # 48 mins, 10s steps
                home_score += random.randint(0, 3)
                away_score += random.randint(0, 3)
                s = {
                    "time_remaining": t,
                    "clock": t, # Added clock
                    "quarter": 1 + (480 - t) // 120,
                    "home_score": home_score,
                    "away_score": away_score,
                    "possession": random.randint(0, 1),
                    "momentum": random.uniform(-1, 1),
                    "pts_scored_this_poss": random.choice([0, 0, 0, 2, 3])
                }
                states.append(s)
            
            f.write(json.dumps({
                "game_id": game_id, 
                "states": states,
                "final_home": home_score,
                "final_away": away_score
            }) + "\n")

if __name__ == "__main__":
    generate_synthetic_games(500)
    print("Generated 500 synthetic games in data/synthetic/games_10k.jsonl")
