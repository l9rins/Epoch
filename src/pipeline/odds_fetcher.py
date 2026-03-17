"""
src/pipeline/odds_fetcher.py
Fetches live NBA moneylines, spreads, and totals from The Odds API.
Feeds directly into /api/odds/today endpoint.

Docs: https://the-odds-api.com/lif-of-sports-apis/soccer/
Key: ODDS_API_KEY in .env
Free tier: 500 requests/month. Cache aggressively.
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────

API_BASE      = "https://api.the-odds-api.com/v4"
SPORT         = "basketball_nba"
REGIONS       = "us"                          # us = DraftKings, FanDuel, BetMGM, etc.
MARKETS       = "h2h,spreads,totals"          # moneyline + spread + total
ODDS_FORMAT   = "american"
DATE_FORMAT   = "iso"

BOOKS_PRIORITY = ["draftkings", "fanduel", "betmgm", "pointsbet", "caesars"]

CACHE_FILE    = Path("data/cache/odds_today.json")
CACHE_TTL_S   = 300                           # 5 minutes — free tier friendly


# ── Public API ────────────────────────────────────────────────────────────────

class OddsFetcher:
    """
    Fetches and caches live NBA odds.
    Falls back to cached data if API is unavailable or key is missing.
    """

    def __init__(self, api_key: Optional[str] = None, cache_ttl: int = CACHE_TTL_S):
        self.api_key  = api_key or os.environ.get("ODDS_API_KEY", "")
        self.cache_ttl = cache_ttl
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)

    # ── Main entry point ──────────────────────────────────────────────────────

    def get_todays_odds(self) -> dict:
        """
        Returns structured odds for today's NBA games.

        Shape:
        {
            "fetched_at": "2026-03-17T06:00:00Z",
            "requests_remaining": 487,
            "games": [
                {
                    "game_id": "abc123",
                    "home_team": "Boston Celtics",
                    "away_team": "Miami Heat",
                    "commence_time": "2026-03-17T23:00:00Z",
                    "markets": {
                        "h2h": {
                            "home": {"best": -165, "books": {"draftkings": -165, "fanduel": -172}},
                            "away": {"best": +140, "books": {"draftkings": +140, "fanduel": +145}},
                        },
                        "spreads": {
                            "home": {"best": -5.5, "best_price": -110, "books": {...}},
                            "away": {"best": +5.5, "best_price": -110, "books": {...}},
                        },
                        "totals": {
                            "over": {"best": 216.5, "best_price": -110, "books": {...}},
                            "under": {"best": 216.5, "best_price": -110, "books": {...}},
                        }
                    }
                }
            ],
            "edges": [
                {
                    "team": "Boston Celtics",
                    "books": [{"name": "DRAFTKINGS", "line": -165, "best": true}, ...],
                    "win_pct": 71
                }
            ]
        }
        """
        # Try cache first
        cached = self._read_cache()
        if cached:
            logger.debug("odds_fetcher: serving from cache")
            return cached

        # No valid cache — fetch live
        if not self.api_key:
            logger.warning("odds_fetcher: ODDS_API_KEY not set — returning empty odds")
            return self._empty_response("ODDS_API_KEY not configured")

        try:
            raw = self._fetch_from_api()
            structured = self._structure(raw["events"], raw.get("requests_remaining", "?"))
            self._write_cache(structured)
            return structured
        except Exception as exc:
            logger.error(f"odds_fetcher: API fetch failed — {exc}")
            # Return stale cache if available, else empty
            stale = self._read_cache(ignore_ttl=True)
            if stale:
                stale["stale"] = True
                return stale
            return self._empty_response(str(exc))

    # ── API call ──────────────────────────────────────────────────────────────

    def _fetch_from_api(self) -> dict:
        url = f"{API_BASE}/sports/{SPORT}/odds"
        params = {
            "apiKey":      self.api_key,
            "regions":     REGIONS,
            "markets":     MARKETS,
            "oddsFormat":  ODDS_FORMAT,
            "dateFormat":  DATE_FORMAT,
        }

        with httpx.Client(timeout=10.0) as client:
            resp = client.get(url, params=params)
            resp.raise_for_status()

        requests_remaining = int(resp.headers.get("x-requests-remaining", -1))
        logger.info(f"odds_fetcher: fetched {len(resp.json())} games | {requests_remaining} requests remaining")

        return {
            "events": resp.json(),
            "requests_remaining": requests_remaining,
        }

    # ── Structuring ───────────────────────────────────────────────────────────

    def _structure(self, events: list, requests_remaining) -> dict:
        games     = []
        edges     = []

        for event in events:
            game_id      = event.get("id", "")
            home_team    = event.get("home_team", "")
            away_team    = event.get("away_team", "")
            commence     = event.get("commence_time", "")
            bookmakers   = event.get("bookmakers", [])

            markets = self._parse_markets(bookmakers, home_team, away_team)

            games.append({
                "game_id":       game_id,
                "home_team":     home_team,
                "away_team":     away_team,
                "commence_time": commence,
                "markets":       markets,
            })

            # Build edge cards (for bettor panel best-odds display)
            h2h = markets.get("h2h", {})
            if h2h:
                for side, team_name in [("home", home_team), ("away", away_team)]:
                    side_data = h2h.get(side, {})
                    books_raw = side_data.get("books", {})
                    if not books_raw:
                        continue

                    best_line = side_data.get("best")
                    books_list = [
                        {
                            "name":  k.upper(),
                            "line":  v,
                            "best":  (v == best_line),
                        }
                        for k, v in books_raw.items()
                        if k in BOOKS_PRIORITY
                    ]
                    # Sort by priority order
                    books_list.sort(key=lambda b: BOOKS_PRIORITY.index(b["name"].lower())
                                    if b["name"].lower() in BOOKS_PRIORITY else 99)

                    # Implied win probability from best American line
                    win_pct = _american_to_implied(best_line) if best_line else 50

                    edges.append({
                        "game_id":  game_id,
                        "team":     team_name,
                        "books":    books_list[:3],          # top 3 books
                        "win_pct":  round(win_pct),
                    })

        return {
            "fetched_at":          datetime.now(timezone.utc).isoformat(),
            "requests_remaining":  requests_remaining,
            "games":               games,
            "edges":               edges,
            "stale":               False,
        }

    def _parse_markets(self, bookmakers: list, home_team: str, away_team: str) -> dict:
        """Aggregate across bookmakers — best line per side per market."""
        h2h_home     = {}   # book → american line
        h2h_away     = {}
        spread_home  = {}   # book → {"point": float, "price": int}
        spread_away  = {}
        total_over   = {}   # book → {"point": float, "price": int}
        total_under  = {}

        for bm in bookmakers:
            key = bm.get("key", "")
            for market in bm.get("markets", []):
                mkey = market.get("key", "")
                for outcome in market.get("outcomes", []):
                    name  = outcome.get("name", "")
                    price = outcome.get("price")
                    point = outcome.get("point")

                    if mkey == "h2h":
                        if name == home_team:
                            h2h_home[key] = price
                        elif name == away_team:
                            h2h_away[key] = price

                    elif mkey == "spreads":
                        if name == home_team:
                            spread_home[key] = {"point": point, "price": price}
                        elif name == away_team:
                            spread_away[key] = {"point": point, "price": price}

                    elif mkey == "totals":
                        if name == "Over":
                            total_over[key] = {"point": point, "price": price}
                        elif name == "Under":
                            total_under[key] = {"point": point, "price": price}

        return {
            "h2h": {
                "home": _best_american(h2h_home, favor="home"),
                "away": _best_american(h2h_away, favor="away"),
            },
            "spreads": {
                "home": _best_spread(spread_home),
                "away": _best_spread(spread_away),
            },
            "totals": {
                "over":  _best_spread(total_over),
                "under": _best_spread(total_under),
            },
        }

    # ── Cache ─────────────────────────────────────────────────────────────────

    def _read_cache(self, ignore_ttl: bool = False) -> Optional[dict]:
        if not CACHE_FILE.exists():
            return None
        try:
            age = time.time() - CACHE_FILE.stat().st_mtime
            if not ignore_ttl and age > self.cache_ttl:
                return None
            with open(CACHE_FILE) as f:
                return json.load(f)
        except Exception:
            return None

    def _write_cache(self, data: dict):
        try:
            with open(CACHE_FILE, "w") as f:
                json.dump(data, f)
        except Exception as exc:
            logger.warning(f"odds_fetcher: cache write failed — {exc}")

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _empty_response(reason: str = "") -> dict:
        return {
            "fetched_at":         datetime.now(timezone.utc).isoformat(),
            "requests_remaining": "?",
            "games":              [],
            "edges":              [],
            "stale":              True,
            "error":              reason,
        }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _best_american(books: dict, favor: str = "home") -> dict:
    """
    Find the best American moneyline across books.
    Best for home = least negative (or most positive).
    Best for away = least negative (or most positive).
    """
    if not books:
        return {}

    # For moneylines, best = highest value (least negative = better for bettor)
    best_key  = max(books, key=lambda k: books[k] if books[k] else -9999)
    best_line = books[best_key]

    return {
        "best":  best_line,
        "books": {k: v for k, v in books.items() if k in BOOKS_PRIORITY},
    }


def _best_spread(books: dict) -> dict:
    """Find best spread price (least negative price) across books."""
    if not books:
        return {}

    best_key = max(books, key=lambda k: books[k].get("price", -9999) if isinstance(books[k], dict) else -9999)
    best     = books[best_key]

    return {
        "best":       best.get("point") if isinstance(best, dict) else None,
        "best_price": best.get("price") if isinstance(best, dict) else None,
        "books":      {k: v for k, v in books.items() if k in BOOKS_PRIORITY},
    }


def _american_to_implied(line: int) -> float:
    """Convert American moneyline to implied win probability (%)."""
    if line is None:
        return 50.0
    if line < 0:
        return (-line) / (-line + 100) * 100
    else:
        return 100 / (line + 100) * 100
