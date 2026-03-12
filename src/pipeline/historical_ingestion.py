import sqlite3
import argparse
import time
from pathlib import Path
from datetime import datetime

class HistoricalIngestion:
    DB_PATH = Path("data/nba_history.db")

    def __init__(self, db_path: str = None):
        self.db_path = Path(db_path) if db_path else self.DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self.create_schema()

    def create_schema(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS games (
                game_id TEXT PRIMARY KEY,
                season TEXT,
                date TEXT,
                home_team TEXT,
                away_team TEXT,
                home_score INTEGER,
                away_score INTEGER,
                winner TEXT,
                home_fg_pct REAL,
                away_fg_pct REAL,
                home_ft_pct REAL,
                away_ft_pct REAL,
                home_3p_pct REAL,
                away_3p_pct REAL,
                home_rebounds INTEGER,
                away_rebounds INTEGER,
                home_assists INTEGER,
                away_assists INTEGER,
                overtime INTEGER DEFAULT 0
            )
        """)
        self.conn.commit()

    def ingest_season(self, season: str):
        """Ingest all games for a given season (e.g. '2023-24')."""
        from nba_api.stats.endpoints import leaguegamefinder

        # Fetch home games  
        time.sleep(1)  # Rate limit
        home_finder = leaguegamefinder.LeagueGameFinder(
            season_nullable=season,
            season_type_nullable="Regular Season",
            league_id_nullable="00"
        )
        home_df = home_finder.get_data_frames()[0]

        if home_df.empty:
            print(f"No games found for {season}")
            return 0

        # Group by GAME_ID — each game has 2 rows (home + away)
        game_ids = home_df["GAME_ID"].unique()
        inserted = 0

        for gid in game_ids:
            rows = home_df[home_df["GAME_ID"] == gid]
            if len(rows) != 2:
                continue

            # Determine home/away by MATCHUP field (vs. = home, @ = away)
            home_row = None
            away_row = None
            for _, row in rows.iterrows():
                matchup = row.get("MATCHUP", "")
                if "vs." in str(matchup):
                    home_row = row
                elif "@" in str(matchup):
                    away_row = row

            if home_row is None or away_row is None:
                continue

            # Check for overtime (MIN > 240 means OT)
            try:
                home_min = float(home_row.get("MIN", 240))
                ot = 1 if home_min > 240 else 0
            except (ValueError, TypeError):
                ot = 0

            home_pts = int(home_row.get("PTS", 0))
            away_pts = int(away_row.get("PTS", 0))
            winner = "HOME" if home_pts > away_pts else "AWAY"

            try:
                self.conn.execute("""
                    INSERT OR IGNORE INTO games VALUES (
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                    )
                """, (
                    gid, season,
                    str(home_row.get("GAME_DATE", "")),
                    str(home_row.get("TEAM_ABBREVIATION", "")),
                    str(away_row.get("TEAM_ABBREVIATION", "")),
                    home_pts, away_pts, winner,
                    float(home_row.get("FG_PCT", 0) or 0),
                    float(away_row.get("FG_PCT", 0) or 0),
                    float(home_row.get("FT_PCT", 0) or 0),
                    float(away_row.get("FT_PCT", 0) or 0),
                    float(home_row.get("FG3_PCT", 0) or 0),
                    float(away_row.get("FG3_PCT", 0) or 0),
                    int(home_row.get("REB", 0) or 0),
                    int(away_row.get("REB", 0) or 0),
                    int(home_row.get("AST", 0) or 0),
                    int(away_row.get("AST", 0) or 0),
                    ot
                ))
                inserted += 1
            except Exception as e:
                continue

        self.conn.commit()
        print(f"Ingested {inserted} games for {season}")
        return inserted

    def ingest_all(self, from_season: str = "2015-16", to_season: str = None):
        """Ingest multiple seasons."""
        # Parse from_season year
        start_year = int(from_season.split("-")[0])
        current_year = datetime.now().year
        # Current season: if month >= 10, it's the new season
        if datetime.now().month >= 10:
            end_year = current_year
        else:
            end_year = current_year - 1

        if to_season:
            end_year = int(to_season.split("-")[0])

        total = 0
        for year in range(start_year, end_year + 1):
            season = f"{year}-{str(year + 1)[-2:]}"
            count = self.ingest_season(season)
            total += count
            time.sleep(2)  # Rate limit between seasons

        print(f"\nIngested {total} games total")
        return total

    def query_head_to_head(self, team1: str, team2: str, last_n: int = 10) -> list:
        """Return last N matchups between two teams."""
        cursor = self.conn.execute("""
            SELECT * FROM games
            WHERE (home_team = ? AND away_team = ?)
               OR (home_team = ? AND away_team = ?)
            ORDER BY date DESC
            LIMIT ?
        """, (team1, team2, team2, team1, last_n))
        
        return [dict(row) for row in cursor.fetchall()]

    def get_game_count(self) -> int:
        cursor = self.conn.execute("SELECT COUNT(*) FROM games")
        return cursor.fetchone()[0]

    def close(self):
        self.conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest historical NBA games")
    parser.add_argument("--seasons", type=int, default=3, 
                        help="Number of recent seasons to ingest")
    args = parser.parse_args()

    current_year = datetime.now().year
    if datetime.now().month < 10:
        current_year -= 1
    start_year = current_year - args.seasons + 1
    from_season = f"{start_year}-{str(start_year + 1)[-2:]}"

    print(f"Ingesting {args.seasons} seasons starting from {from_season}...")
    ingestion = HistoricalIngestion()
    ingestion.ingest_all(from_season=from_season)
    
    total = ingestion.get_game_count()
    print(f"\nTotal games in database: {total}")

    # Sample H2H query
    print("\n--- GSW vs LAL Last 5 Games ---")
    h2h = ingestion.query_head_to_head("GSW", "LAL", last_n=5)
    for g in h2h:
        print(f"  {g['date']}: {g['home_team']} {g['home_score']} - {g['away_score']} {g['away_team']} -> {g['winner']}")
    
    if not h2h:
        print("  No matchups found (data may not include these teams)")
    
    ingestion.close()
