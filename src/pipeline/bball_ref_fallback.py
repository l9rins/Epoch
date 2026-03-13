import requests
from bs4 import BeautifulSoup
import logging

def fetch_bball_ref_standings() -> dict:
    """Fetch 2024-25 NBA standings from Basketball Reference."""
    url = "https://www.basketball-reference.com/leagues/NBA_2025_standings.html"
    try:
        # User Rule: Never hit the real network in tests (handled in pytest mocks)
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return parse_bball_ref_standings(response.text)
    except Exception as e:
        logging.error(f"Basketball Reference fallback fetch failed: {e}")
        return {}

def parse_bball_ref_standings(html_content: str) -> dict:
    """Parse standings HTML into a dictionary of team stats."""
    if not html_content:
        return {}
        
    soup = BeautifulSoup(html_content, "html.parser")
    standings = {}
    
    # Basketball Reference uses confs_standings_E and confs_standings_W for basic W/L
    for table_id in ["confs_standings_E", "confs_standings_W"]:
        table = soup.find("table", {"id": table_id})
        if not table:
            continue
            
        rows = table.find_all("tr", class_="full_table")
        for row in rows:
            team_cell = row.find("th", {"data-stat": "team_name"})
            wins_cell = row.find("td", {"data-stat": "wins"})
            losses_cell = row.find("td", {"data-stat": "losses"})
            
            if team_cell and wins_cell and losses_cell:
                # Clean team name (remove playoff markers like * or seeds)
                team_name = team_cell.text.strip().replace("*", "")
                if "(" in team_name:
                    team_name = team_name.split("(")[0].strip()
                
                try:
                    standings[team_name] = {
                        "wins": int(wins_cell.text),
                        "losses": int(losses_cell.text),
                        "source": "basketball_reference_fallback"
                    }
                except (ValueError, TypeError):
                    continue
                    
    return standings
