import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

@dataclass
class RefTendency:
    ref_name: str
    avg_total_points: float     # avg total pts in their games
    avg_fouls_per_game: float
    pace_factor: float          # 0.8=slow, 1.0=neutral, 1.2=fast
    games_officiated: int

class RefereeModel:
    # League average total points (~224 in modern NBA)
    LEAGUE_AVG_TOTAL = 224.0

    def __init__(self, db_path: str = None):
        from src.pipeline.historical_ingestion import HistoricalIngestion
        self.db_path = db_path or str(HistoricalIngestion.DB_PATH)
        
        # Referee data is stored in a separate table
        db = Path(self.db_path)
        db.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(db))
        self.conn.row_factory = sqlite3.Row
        self._ensure_ref_table()

    def _ensure_ref_table(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS ref_games (
                game_id TEXT,
                ref_name TEXT,
                total_points INTEGER,
                total_fouls INTEGER,
                pace REAL,
                PRIMARY KEY (game_id, ref_name)
            )
        """)
        self.conn.commit()

    def ingest_ref_data(self, game_id: str, ref_names: List[str], 
                        total_points: int, total_fouls: int = 40, pace: float = 1.0):
        """Store referee assignment for a game."""
        for ref in ref_names:
            try:
                self.conn.execute("""
                    INSERT OR IGNORE INTO ref_games VALUES (?, ?, ?, ?, ?)
                """, (game_id, ref.strip(), total_points, total_fouls, pace))
            except Exception:
                continue
        self.conn.commit()

    def get_ref_tendency(self, ref_name: str) -> RefTendency:
        """Calculate tendency profile for a referee."""
        cursor = self.conn.execute("""
            SELECT AVG(total_points) as avg_pts,
                   AVG(total_fouls) as avg_fouls,
                   AVG(pace) as avg_pace,
                   COUNT(*) as games
            FROM ref_games
            WHERE ref_name = ?
        """, (ref_name,))
        
        row = cursor.fetchone()
        
        if row is None or row["games"] == 0:
            # Unknown ref — return neutral tendency
            return RefTendency(
                ref_name=ref_name,
                avg_total_points=self.LEAGUE_AVG_TOTAL,
                avg_fouls_per_game=40.0,
                pace_factor=1.0,
                games_officiated=0
            )

        # Pace factor: how much this ref's games deviate from league average
        avg_pts = float(row["avg_pts"])
        pace_factor = avg_pts / self.LEAGUE_AVG_TOTAL
        # Clamp to reasonable range
        pace_factor = max(0.5, min(1.5, pace_factor))

        return RefTendency(
            ref_name=ref_name,
            avg_total_points=round(avg_pts, 1),
            avg_fouls_per_game=round(float(row["avg_fouls"]), 1),
            pace_factor=round(pace_factor, 3),
            games_officiated=int(row["games"])
        )

    def adjust_prediction(self, base_prediction: dict, 
                          ref_names: List[str]) -> dict:
        """Adjust a prediction based on referee crew tendencies."""
        prediction = dict(base_prediction)  # Don't mutate original

        if not ref_names:
            prediction["referee_pace_factor"] = 1.0
            return prediction

        # Get tendencies for all refs in the crew
        tendencies = [self.get_ref_tendency(ref) for ref in ref_names]
        
        # Average pace factor across crew
        avg_pace = sum(t.pace_factor for t in tendencies) / len(tendencies)
        
        # Adjust predicted total
        base_total = prediction.get("predicted_total", 220)
        adjusted_total = round(base_total * avg_pace)
        
        prediction["predicted_total"] = adjusted_total
        prediction["referee_pace_factor"] = round(avg_pace, 3)
        
        return prediction

    def close(self):
        self.conn.close()
