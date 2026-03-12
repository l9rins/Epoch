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
                    
                # Synthetic Vision Features
                # Spacing (0-100), Density (0-10), Coverage (0-100)
                spacing = random.normalvariate(50, 15)
                spacing = max(0, min(100, spacing))
                
                density = random.normalvariate(4, 2)
                density = max(0, min(10, density))
                
                coverage = random.normalvariate(60, 20)
                coverage = max(0, min(100, coverage))
                
                # Binary events (frequency based on game state/pace)
                is_fast_break = 1 if random.random() < (base_pace / 500) else 0
                is_open_shooter = 1 if random.random() < (spacing / 500) else 0
                is_pick_roll = 1 if random.random() < 0.15 else 0
                
                # Fatigue (Home/Away)
                home_fresh = random.random() > 0.1 # 10% chance of B2B
                away_fresh = random.random() > 0.1
                
                # Q1=1.0, Q2=0.97, Q3=0.94, Q4=0.90
                q_multi = {1: 1.0, 2: 0.97, 3: 0.94, 4: 0.90}.get(q, 0.90)
                home_fatigue = q_multi - (0.05 if not home_fresh else 0)
                away_fatigue = q_multi - (0.05 if not away_fresh else 0)

                # Scoring logic adjustment based on vision features
                # Efficiency boost for fast break or open shooter
                eff_mod = 1.0
                if is_fast_break: eff_mod *= 1.4
                if is_open_shooter: eff_mod *= 1.3
                if spacing > 70: eff_mod *= 1.1
                if density > 7: eff_mod *= 0.8 # Clogged paint hurts scoring
                
                mod_efficiency = base_efficiency * eff_mod
                
                # Scoring Probability based on adjusted efficiency
                # 0 pts, 2 pts, or 3 pts
                r = random.random()
                three_prob = 0.15 * (1.5 if is_open_shooter else 1.0)
                two_prob = 0.35 * (1.2 if is_fast_break else 0.9 if density > 7 else 1.0)
                
                if r < (1.0 - (three_prob + two_prob)):
                    pts = 0
                elif r < (1.0 - three_prob):
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
                    "pts_scored_this_poss": pts,
                    "defensive_spacing": round(spacing, 1),
                    "paint_density": round(density, 1),
                    "three_point_coverage": round(coverage, 1),
                    "pick_roll": is_pick_roll,
                    "fast_break": is_fast_break,
                    "open_shooter": is_open_shooter,
                    "fatigue_home": round(home_fatigue, 2),
                    "fatigue_away": round(away_fatigue, 2)
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
