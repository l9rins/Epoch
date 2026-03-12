import json
import random
from pathlib import Path

# Need fake games that generate 500 game states (ticks) each
# We don't need a perfect simulator, just something that looks like an NBA game dynamically unfolding

def generate_synthetic_games(num_games=10000, output_file="data/synthetic/games_10k.jsonl"):
    out_path = Path(output_file)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Simple probability distributions
    # Pace: target 98.5 possessions per game, so ~197 total possessions. Time per poss is ~48 mins / 197 = ~14.6s per poss
    # Each game state is logged every 500ms, but for synthetic data, we can just jump possession by possession to build the sequence, or jump 5-10s at a time.
    # To save massive file sizes, we'll log ~100 states per game representing key moments or regular intervals. 
    # For training, sequences of score and time matter most.
    
    with open(out_path, "w") as f:
        for game_idx in range(num_games):
            # Game parameters variation
            base_pace = random.normalvariate(98.5, 4.0)
            base_efficiency = random.normalvariate(1.14, 0.05) # ~1.14 pts per poss
            
            home_score = 0
            away_score = 0
            
            states = []
            
            total_seconds = 4 * 720 # 2880
            current_time = 0
            possession = random.randint(0, 1) # Randomize tipoff winner
            
            while current_time < total_seconds:
                # Time elapsed this possession
                poss_time = max(4.0, random.normalvariate(2880 / (base_pace * 2), 4.0))
                current_time += poss_time
                if current_time > total_seconds:
                    current_time = total_seconds
                    
                time_remaining = total_seconds - current_time
                
                # Determine quarter and clock
                if time_remaining > 2160:
                    q = 1
                    clk = time_remaining - 2160
                elif time_remaining > 1440:
                    q = 2
                    clk = time_remaining - 1440
                elif time_remaining > 720:
                    q = 3
                    clk = time_remaining - 720
                else:
                    q = 4
                    clk = time_remaining
                    
                # Scoring
                # 0 pts ~ 50%, 2 pts ~ 35%, 3 pts ~ 15%
                r = random.random()
                if r < 0.50:
                    pts = 0
                elif r < 0.85:
                    pts = 2
                else:
                    pts = 3
                    
                if possession == 0:
                    home_score += pts
                    possession = 1
                else:
                    away_score += pts
                    possession = 0
                    
                state_dict = {
                    "game_id": game_idx,
                    "quarter": q,
                    "clock": clk,
                    "home_score": home_score,
                    "away_score": away_score,
                    "possession": possession,
                    "time_remaining": time_remaining,
                    "pts_scored_this_poss": pts
                }
                states.append(state_dict)
                
                # We can sample every ~30 seconds for the ML rather than every second to save size
            
            f.write(json.dumps({"game_id": game_idx, "states": states, "final_home": home_score, "final_away": away_score}) + "\n")
            
            if (game_idx + 1) % 1000 == 0:
                print(f"Generated {game_idx + 1} games...")

if __name__ == "__main__":
    print("Generating 10,000 synthetic games for ML training...")
    generate_synthetic_games()
    print("Done. Saved to data/synthetic/games_10k.jsonl")
