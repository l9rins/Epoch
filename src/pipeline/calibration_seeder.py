from pathlib import Path
import json
import time
from nba_api.stats.endpoints import leaguegamefinder
from src.ml.calibration import CalibrationEngine

def seed_calibration_history(seasons=None, output_path=None):
    if seasons is None:
        seasons = ["2022-23", "2023-24", "2024-25"]
    if output_path is None:
        output_path = Path("data/calibration_history.jsonl")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Skip if already seeded
    if output_path.exists():
        try:
            with open(output_path, "r") as f:
                existing = sum(1 for _ in f)
            if existing >= 50:
                print(f"Already seeded ({existing} samples). Skipping.")
                return existing
        except Exception:
            pass

    samples = []

    for season in seasons:
        print(f"Fetching {season} game results...")
        try:
            finder = leaguegamefinder.LeagueGameFinder(
                season_nullable=season,
                league_id_nullable="00",
                season_type_nullable="Regular Season"
            )
            games_df = finder.get_data_frames()[0]
            time.sleep(1)  # rate limit respect
        except Exception as e:
            print(f"Error fetching {season}: {e}")
            continue

        # Filter to home games only to avoid duplicates
        # NBA API MATCHUP format is "TEAM1 vs. TEAM2" for home games
        home_games = games_df[games_df["MATCHUP"].str.contains("vs\.")].copy()

        # Build season win pct lookup
        team_wins = {}
        team_games = {}
        for _, row in games_df.iterrows():
            abbr = row["TEAM_ABBREVIATION"]
            won = 1 if row["WL"] == "W" else 0
            team_wins[abbr] = team_wins.get(abbr, 0) + won
            team_games[abbr] = team_games.get(abbr, 0) + 1

        team_win_pct = {
            abbr: team_wins[abbr] / team_games[abbr]
            for abbr in team_wins if team_games[abbr] > 0
        }

        for _, row in home_games.iterrows():
            try:
                home_abbr = row["TEAM_ABBREVIATION"]
                # Extract away team from matchup string "HOME vs. AWAY"
                matchup = row["MATCHUP"]
                away_abbr = matchup.split("vs. ")[-1].strip()

                home_pct = team_win_pct.get(home_abbr, 0.5)
                away_pct = team_win_pct.get(away_abbr, 0.5)

                # Naive but calibrated baseline probability
                base_prob = 0.57 + (home_pct - away_pct) * 0.5
                base_prob = max(0.15, min(0.85, base_prob))

                actual = 1 if row["WL"] == "W" else 0

                samples.append({
                    "predicted": round(base_prob, 4),
                    "actual": actual,
                    "season": season,
                    "game_id": str(row.get("GAME_ID", "")),
                })
            except Exception:
                continue

    if not samples:
        print("No samples collected. Check nba_api connection.")
        return 0

    # Write to JSONL
    with open(output_path, "w") as f:
        for s in samples:
            f.write(json.dumps({"predicted": s["predicted"], "actual": s["actual"]}) + "\n")

    print(f"Written {len(samples)} calibration samples to {output_path}")

    # Activate Platt scaling immediately
    engine = CalibrationEngine(history_file=str(output_path))
    engine.recalibrate()
    report = engine.accuracy_report()
    print(f"Brier Score: {report['brier_score']:.4f} (target < 0.18)")
    print(f"Beating ESPN BPI: {report['beating_espn_bpi']}")

    return len(samples)

if __name__ == "__main__":
    seed_calibration_history()
