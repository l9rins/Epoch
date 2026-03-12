from pathlib import Path
from datetime import datetime, timedelta
import json
from collections import defaultdict

def build_fatigue_context(schedule: list) -> dict:
    """
    Given a list of game dicts with keys:
    {game_date, home_team, away_team}
    Returns a dict keyed by '{team}_{date}' with fatigue context.
    """
    # Build per-team sorted game list
    team_games = defaultdict(list)
    for game in schedule:
        date = game["game_date"]
        team_games[game["home_team"]].append(date)
        team_games[game["away_team"]].append(date)

    for team in team_games:
        team_games[team] = sorted(set(team_games[team]))

    fatigue_context = {}

    for team, dates in team_games.items():
        for i, date_str in enumerate(dates):
            current = datetime.strptime(date_str, "%Y-%m-%d")

            # Rest days
            if i == 0:
                rest_days = 7
            else:
                prev = datetime.strptime(dates[i - 1], "%Y-%m-%d")
                rest_days = min((current - prev).days, 7)

            # Back to back
            is_b2b = rest_days == 1

            # Games in last 7 days
            window_start = current - timedelta(days=7)
            games_last_7 = sum(
                1 for d in dates[:i]
                if datetime.strptime(d, "%Y-%m-%d") >= window_start
            )

            key = f"{team}_{date_str}"
            fatigue_context[key] = {
                "team": team,
                "date": date_str,
                "rest_days": rest_days,
                "is_back_to_back": is_b2b,
                "games_last_7_days": games_last_7,
            }

    return fatigue_context

def get_fatigue_context(team_abbr: str, game_date: str,
                         context_path: str = "data/fatigue_context.json") -> dict:
    """
    Returns fatigue context for a specific team on a specific date.
    Falls back to neutral values if not found.
    """
    path = Path(context_path)
    if not path.exists():
        return {"rest_days": 3, "is_back_to_back": False, "games_last_7_days": 3}

    try:
        with open(path) as f:
            context = json.load(f)
    except Exception:
        return {"rest_days": 3, "is_back_to_back": False, "games_last_7_days": 3}

    key = f"{team_abbr}_{game_date}"
    return context.get(key, {
        "rest_days": 3,
        "is_back_to_back": False,
        "games_last_7_days": 3,
    })

def run_fatigue_seeder():
    from nba_api.stats.endpoints import leaguegamefinder
    import json
    from pathlib import Path
    import time

    print("Fetching full 2024-25 NBA schedule...")
    try:
        finder = leaguegamefinder.LeagueGameFinder(
            season_nullable="2024-25",
            league_id_nullable="00",
            season_type_nullable="Regular Season"
        )
        games_df = finder.get_data_frames()[0]
        
        schedule = []
        # Group by game_id to get only one record per game
        for game_id, group in games_df.groupby("GAME_ID"):
            if len(group) == 2:
                # One record for each team in the game
                row_home = group[group["MATCHUP"].str.contains(" vs. ")]
                row_away = group[group["MATCHUP"].str.contains(" @ ")]
                
                if not row_home.empty and not row_away.empty:
                    schedule.append({
                        "game_date": row_home.iloc[0]["GAME_DATE"],
                        "home_team": row_home.iloc[0]["TEAM_ABBREVIATION"],
                        "away_team": row_away.iloc[0]["TEAM_ABBREVIATION"]
                    })
        
        # Sort by date
        schedule.sort(key=lambda x: x["game_date"])

    except Exception as e:
        print(f"Error fetching schedule: {e}")
        return

    if not schedule:
        print("No schedule data returned.")
        return

    print(f"Building fatigue context for {len(schedule)} games...")
    context = build_fatigue_context(schedule)

    output_path = Path("data/fatigue_context.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(context, f, indent=2)

    print(f"Fatigue context saved: {len(context)} team-game entries")
    print("Task 2 OK")

if __name__ == "__main__":
    run_fatigue_seeder()
