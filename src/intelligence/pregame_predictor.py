import os
import sys
import json
import uuid
import argparse
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.binary.ros_reader import load_ros, read_all_players, build_name_pool
from src.intelligence.win_probability import WinProbabilityModel
from src.ml.calibration import CalibrationEngine
from src.simulation.memory_reader import GameState

@dataclass
class Prediction:
    game_id: str
    home_team: str
    away_team: str
    predicted_home_win_prob: float
    predicted_total: int
    timestamp: str
    actual_home_score: int = None
    actual_away_score: int = None
    actual_winner: str = None

class PregamePredictor:
    def __init__(self):
        self.win_model = WinProbabilityModel()
        self.cal_engine = CalibrationEngine()
        self.predictions_dir = Path("data/predictions")
        self.predictions_dir.mkdir(parents=True, exist_ok=True)

    def get_team_strength(self, team_abbr: str) -> float:
        """Calculate team strength from POC file, filtering by the team's roster JSON."""
        data_dir = Path("data")
        poc_file = data_dir / f"{team_abbr.lower()}_poc.ros"
        roster_json = data_dir / f"{team_abbr.lower()}_roster.json"
        
        if not poc_file.exists() or not roster_json.exists():
            return 50.0
        
        try:
            # Load the names of players actually on this team
            with open(roster_json, "r") as f:
                team_roster = json.load(f)
            # Create a list of lowercase name parts for each player
            # (e.g., "Stephen Curry" -> {"stephen", "curry"})
            roster_name_parts = []
            for full_name in team_roster.keys():
                roster_name_parts.append(set(full_name.lower().split()))
                
            data = load_ros(str(poc_file))
            name_pool = build_name_pool(data)
            players = read_all_players(data, name_pool)
            
            skill_ratings = []
            for p in players:
                # 1. Check if the fragment name matches any player on the roster
                # Fragments in ROS name pool can be first or last name
                if p.name:
                    p_name_lower = p.name.lower()
                    match_found = False
                    for parts in roster_name_parts:
                        if p_name_lower in parts:
                            match_found = True
                            break
                    
                    if match_found:
                        sht3pt = p.skills[3]   # SSht3PT
                        sht_mr = p.skills[2]   # SShtMR  
                        sht_ft = p.skills[4]   # SShtFT
                        
                        # Only use players whose skills were actually updated
                        # (not at default 25)
                        if sht3pt > 25 or sht_mr > 25 or sht_ft > 25:
                            avg = (sht3pt + sht_mr + sht_ft) / 3
                            skill_ratings.append(avg)
            
            if not skill_ratings:
                return 50.0
                
            avg_rating = sum(skill_ratings) / len(skill_ratings)
            # Convert 25-110 rating to 0-100 strength
            strength = ((avg_rating - 25) / 85) * 100
            return round(strength, 1)
            
        except Exception:
            return 50.0

    def predict(self, home_team: str, away_team: str) -> dict:
        home_strength = self.get_team_strength(home_team)
        away_strength = self.get_team_strength(away_team)
        
        # Base probability from WinProbabilityModel at tipoff
        # (0-0, Q1, 720s)
        dummy_state = GameState(timestamp=0, quarter=1, clock=720.0, home_score=0, away_score=0, possession=0)
        base_prob = self.win_model(dummy_state)
        
        # Adjustment: 0.50 + (strength_diff * 0.01)
        # But we use our base_prob which might include home bias
        strength_diff = home_strength - away_strength
        adj_prob = base_prob + (strength_diff * 0.01)
        
        # Clamp 0.20 to 0.80
        final_prob = max(0.20, min(0.80, adj_prob))
        
        prediction = {
            "game_id": str(uuid.uuid4())[:8],
            "home_team": home_team,
            "away_team": away_team,
            "predicted_home_win_prob": round(float(final_prob), 3),
            "predicted_total": 220,  # Placeholder
            "timestamp": datetime.now().isoformat(),
            "actual_home_score": None,
            "actual_away_score": None,
            "actual_winner": None
        }
        return prediction

    def log_prediction(self, prediction: dict):
        date_str = datetime.now().strftime("%Y-%m-%d")
        log_file = self.predictions_dir / f"{date_str}.jsonl"
        
        with open(log_file, "a") as f:
            f.write(json.dumps(prediction) + "\n")
        print(f"Prediction logged to {log_file}")

    def record_result(self, game_id: str, home_score: int, away_score: int):
        """Find prediction by game_id and record actual results."""
        for log_file in self.predictions_dir.glob("*.jsonl"):
            lines = log_file.read_text().splitlines()
            new_lines = []
            found_in_file = False
            target_pred = None

            for line in lines:
                pred = json.loads(line)
                if pred["game_id"] == game_id:
                    pred["actual_home_score"] = home_score
                    pred["actual_away_score"] = away_score
                    home_won = home_score > away_score
                    pred["actual_winner"] = "HOME" if home_won else "AWAY"
                    
                    # Update calibration engine
                    self.cal_engine.log_outcome(pred["predicted_home_win_prob"], home_won)
                    
                    target_pred = pred
                    found_in_file = True
                    new_lines.append(json.dumps(pred))
                else:
                    new_lines.append(line)
            
            if found_in_file:
                log_file.write_text("\n".join(new_lines) + "\n")
                print(f"Result recorded for game {game_id} in {log_file}")
                return target_pred
        
        print(f"Error: Game ID {game_id} not found in predictions.")
        return None

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--home", type=str)
    parser.add_argument("--away", type=str)
    parser.add_argument("--predict", action="store_true")
    parser.add_argument("--game-id", type=str)
    parser.add_argument("--home-score", type=int)
    parser.add_argument("--away-score", type=int)
    parser.add_argument("--result", action="store_true")
    args = parser.parse_args()

    predictor = PregamePredictor()

    if args.predict:
        if not args.home or not args.away:
            print("Error: --home and --away required for prediction.")
        else:
            pred = predictor.predict(args.home, args.away)
            print(f"PREDICTION: {pred['home_team']} vs {pred['away_team']}")
            print(f"WIN PROB: {pred['predicted_home_win_prob']:.1%}")
            predictor.log_prediction(pred)
            print(f"GAME ID: {pred['game_id']}")

    if args.result:
        if not args.game_id or args.home_score is None or args.away_score is None:
            print("Error: --game-id, --home-score, --away-score required for result.")
        else:
            predictor.record_result(args.game_id, args.home_score, args.away_score)
