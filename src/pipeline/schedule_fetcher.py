import sys
from pathlib import Path
from nba_api.stats.endpoints import scoreboardv2
from nba_api.stats.static import teams as nba_teams_static
from datetime import datetime

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.intelligence.pregame_predictor import PregamePredictor

class ScheduleFetcher:
    def __init__(self):
        self.predictor = PregamePredictor()
        self.team_map = {t["id"]: t["abbreviation"] for t in nba_teams_static.get_teams()}

    def get_todays_games(self) -> list:
        """Fetch today's games from NBA API."""
        print("Fetching today's NBA schedule...")
        try:
            # ScoreboardV2 returns GameHeader as the first result set
            sb = scoreboardv2.ScoreboardV2()
            games_data = sb.get_dict()["resultSets"][0]["rowSet"]
            headers = sb.get_dict()["resultSets"][0]["headers"]
            
            games = []
            home_idx = headers.index("HOME_TEAM_ID")
            away_idx = headers.index("VISITOR_TEAM_ID")
            game_id_idx = headers.index("GAME_ID")
            
            for row in games_data:
                home_abbr = self.team_map.get(row[home_idx])
                away_abbr = self.team_map.get(row[away_idx])
                
                if home_abbr and away_abbr:
                    games.append({
                        "home": home_abbr,
                        "away": away_abbr,
                        "game_id": row[game_id_idx]
                    })
            return games
        except Exception as e:
            print(f"Error fetching schedule: {e}")
            return []

    def predict_all_todays_games(self):
        games = self.get_todays_games()
        if not games:
            print("No games found for today.")
            return

        print("\n" + "="*60)
        print(f"{'HOME':<15} {'AWAY':<15} {'WIN PROB':<12} {'GAME ID'}")
        print("-" * 60)
        
        for g in games:
            pred = self.predictor.predict(g["home"], g["away"])
            # Override generated UUID with real NBA GAME_ID for easier tracking
            pred["game_id"] = g["game_id"]
            self.predictor.log_prediction(pred)
            
            print(f"{g['home']:<15} {g['away']:<15} {pred['predicted_home_win_prob']:>8.1%}     {g['game_id']}")
        print("="*60 + "\n")

if __name__ == "__main__":
    fetcher = ScheduleFetcher()
    fetcher.predict_all_todays_games()
