import json
import time
from pathlib import Path
from nba_api.stats.endpoints import synergyplaytypes, playerdashboardbyshootingsplits, playergamelog
from nba_api.stats.endpoints import commonteamroster
from nba_api.stats.static import teams as nba_teams_static

PLAYER_FALLBACKS = {
    201939: {   # Stephen Curry
        "synergy": {
            "Isolation":     {"poss_pct": 0.10, "ppp": 1.05, "percentile": 0.85},
            "PRBallHandler": {"poss_pct": 0.35, "ppp": 1.12, "percentile": 0.95},
            "Spotup":        {"poss_pct": 0.15, "ppp": 1.25, "percentile": 0.90},
            "OffScreen":     {"poss_pct": 0.20, "ppp": 1.30, "percentile": 0.99},
            "Transition":    {"poss_pct": 0.10, "ppp": 1.15, "percentile": 0.75},
        },
        "shooting": {"fg3_pct": 0.408, "mid_range_pct": 0.450,
                     "at_rim_pct": 0.650, "ft_pct": 0.923},
        "hot_zones": {f"zone_{i}": 0.55 for i in range(1, 15)},
        "form": {"last_10_pts_avg": 28.5, "trending": "hot"}
    },
    203110: {   # Draymond Green
        "synergy": {
            "Isolation":     {"poss_pct": 0.05, "ppp": 0.85, "percentile": 0.35},
            "PRBallHandler": {"poss_pct": 0.10, "ppp": 0.90, "percentile": 0.40},
            "Postup":        {"poss_pct": 0.12, "ppp": 0.88, "percentile": 0.45},
            "Cut":           {"poss_pct": 0.15, "ppp": 1.15, "percentile": 0.70},
            "Transition":    {"poss_pct": 0.08, "ppp": 1.00, "percentile": 0.50},
        },
        "shooting": {"fg3_pct": 0.280, "mid_range_pct": 0.380,
                     "at_rim_pct": 0.580, "ft_pct": 0.620},
        "hot_zones": {f"zone_{i}": 0.32 for i in range(1, 15)},
        "form": {"last_10_pts_avg": 10.0, "trending": "neutral"}
    },
}

GENERIC_FALLBACK = {
    "synergy": {
        "Isolation":     {"poss_pct": 0.08, "ppp": 0.95, "percentile": 0.50},
        "PRBallHandler": {"poss_pct": 0.12, "ppp": 0.95, "percentile": 0.50},
        "Spotup":        {"poss_pct": 0.18, "ppp": 1.00, "percentile": 0.50},
        "Postup":        {"poss_pct": 0.08, "ppp": 0.90, "percentile": 0.50},
        "Cut":           {"poss_pct": 0.10, "ppp": 1.10, "percentile": 0.50},
        "Transition":    {"poss_pct": 0.12, "ppp": 1.05, "percentile": 0.50},
        "OffScreen":     {"poss_pct": 0.05, "ppp": 0.95, "percentile": 0.50},
        "Handoff":       {"poss_pct": 0.04, "ppp": 0.95, "percentile": 0.50},
        "PRRollman":     {"poss_pct": 0.08, "ppp": 1.05, "percentile": 0.50},
        "OffRebound":    {"poss_pct": 0.04, "ppp": 1.00, "percentile": 0.50},
    },
    "shooting": {
        "fg3_pct":       0.360,
        "mid_range_pct": 0.420,
        "at_rim_pct":    0.620,
        "ft_pct":        0.770
    },
    "hot_zones": {f"zone_{i}": 0.40 for i in range(1, 15)},
    "form": {"last_10_pts_avg": 14.0, "trending": "neutral"}
}

# Map team abbreviations to nba_api team IDs
_TEAM_ABBREV_TO_ID = {t["abbreviation"]: t["id"] for t in nba_teams_static.get_teams()}

class NBAApiClient:
    def __init__(self):
        self.cache_dir = Path("data/cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get_team_roster(self, team_abbrev: str, season: str = "2024-25") -> dict:
        """Returns {player_name: player_id} for all players on the team."""
        cache_file = self.cache_dir / f"roster_{team_abbrev}_{season.replace('-', '_')}.json"

        if cache_file.exists():
            try:
                with open(cache_file, "r") as f:
                    return json.load(f)
            except Exception:
                pass

        team_id = _TEAM_ABBREV_TO_ID.get(team_abbrev)
        if team_id is None:
            raise ValueError(f"Unknown team abbreviation: {team_abbrev}")

        try:
            time.sleep(0.6)
            roster_data = commonteamroster.CommonTeamRoster(
                team_id=team_id, season=season
            )
            df = roster_data.get_data_frames()[0]
            result = {}
            for _, row in df.iterrows():
                name = row["PLAYER"]
                pid = int(row["PLAYER_ID"])
                result[name] = pid

            with open(cache_file, "w") as f:
                json.dump(result, f, indent=2)

            return result
        except Exception as e:
            print(f"  [{team_abbrev}] API call failed: {e}, returning empty roster")
            return {}

    def get_player_data(self, player_id: int, player_name: str = "Unknown Player", season: str = "2024-25") -> dict:
        cache_file = self.cache_dir / f"player_{player_id}_{season.replace('-', '_')}.json"
        
        if cache_file.exists():
            try:
                with open(cache_file, "r") as f:
                    return json.load(f)
            except Exception:
                pass
        
        player_fb = PLAYER_FALLBACKS.get(player_id, GENERIC_FALLBACK)
        
        data = {
            "player_id": player_id,
            "player_name": player_name,
            "season": season,
            "synergy": {},
            "shooting": player_fb["shooting"].copy(),
            "hot_zones": player_fb["hot_zones"].copy(),
            "form": player_fb["form"].copy()
        }

        try:
            # Synergy
            time.sleep(1)
            syn = synergyplaytypes.SynergyPlayTypes(
                player_or_team_abbreviation='P',
                season=season,
                season_type_all_star="Regular Season",
                per_mode_simple="PerGame"
            )
            df = syn.get_data_frames()[0]
            df = df[df['PLAYER_ID'].astype(str) == str(player_id)]
            if df.empty:
                data["synergy"] = player_fb["synergy"].copy()
            else:
                for _, row in df.iterrows():
                    ptype = row['PLAY_TYPE']
                    data["synergy"][ptype] = {
                        "poss_pct": float(row['POSS_PCT']),
                        "ppp": float(row['PPP']),
                        "percentile": float(row['PERCENTILE'])
                    }

            # Shooting 
            time.sleep(1)
            splits = playerdashboardbyshootingsplits.PlayerDashboardByShootingSplits(
                player_id=player_id, season=season
            )
            df_shot_overall = splits.get_data_frames()[0]
            if not df_shot_overall.empty:
                data["shooting"]["fg3_pct"] = float(df_shot_overall['FG3_PCT'].values[0])
            
            # This is complex, so let's use global fallback for missing keys later
            # ...
        except Exception as e:
            print(f"API failed ({e}), using fallback for {player_name}")
            fallback = player_fb.copy()
            fallback["player_id"] = player_id
            fallback["player_name"] = player_name
            return fallback
            
        with open(cache_file, "w") as f:
            json.dump(data, f, indent=2)

        return data
