"""
Injury Detector — SESSION B
Monitors beat reporter sentiment for mid-game injury signals.

Confidence tiers:
  T1 — Official NBA injury report API
  T2 — Verified beat reporter tweet (>50k followers)
  T3 — General Twitter/X mention

Pure functions only. No class state.
Twitter access requires TWITTER_BEARER_TOKEN in environment.
"""

from __future__ import annotations

import os
import re
import logging
import time
from typing import Any

import requests

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants — no magic numbers
# ---------------------------------------------------------------------------
TIER_1_SOURCE: str = "nba_official"
TIER_2_SOURCE: str = "beat_reporter"
TIER_3_SOURCE: str = "general_mention"

TIER_1_CONFIDENCE: int = 1
TIER_2_CONFIDENCE: int = 2
TIER_3_CONFIDENCE: int = 3

VERIFIED_FOLLOWER_THRESHOLD: int = 50_000
SEARCH_WINDOW_MINUTES: int = 10
REQUEST_TIMEOUT_SECONDS: int = 10
MAX_RESULTS_PER_QUERY: int = 20

INJURY_KEYWORDS: list[str] = [
    "locker room",
    "ruled out",
    "limping",
    "DNR",
    "did not return",
    "questionable",
    "out for",
    "being evaluated",
    "trainers",
]

# Official NBA injury report endpoint
NBA_INJURY_REPORT_URL: str = (
    "https://stats.nba.com/stats/leaguegamelog"
    "?Counter=0&DateFrom=&DateTo=&Direction=DESC"
    "&LeagueID=00&PlayerOrTeam=T&Season=2024-25"
    "&SeasonType=Regular+Season&Sorter=DATE"
)

TWITTER_SEARCH_URL: str = "https://api.twitter.com/2/tweets/search/recent"
TWITTER_USER_URL: str = "https://api.twitter.com/2/users/by/username/{username}"


# ---------------------------------------------------------------------------
# Data structures (typed dicts — no classes)
# ---------------------------------------------------------------------------

def _make_injury_signal(
    player_name: str,
    tier: int,
    source: str,
    keyword_matched: str,
    raw_text: str,
    confidence_score: float,
    source_followers: int = 0,
) -> dict[str, Any]:
    return {
        "player_name": player_name,
        "tier": tier,
        "source": source,
        "keyword_matched": keyword_matched,
        "raw_text": raw_text,
        "confidence_score": confidence_score,
        "source_followers": source_followers,
        "detected_at_ts": time.time(),
    }


# ---------------------------------------------------------------------------
# Twitter helpers
# ---------------------------------------------------------------------------

def _bearer_header() -> dict[str, str]:
    token = os.environ.get("TWITTER_BEARER_TOKEN", "")
    if not token:
        logger.warning("TWITTER_BEARER_TOKEN not set — Twitter scan disabled")
    return {"Authorization": f"Bearer {token}"}


def _build_query(player_name: str) -> str:
    """Build Twitter search query for a player + injury keywords."""
    kw_or = " OR ".join(f'"{kw}"' for kw in INJURY_KEYWORDS)
    return f'"{player_name}" ({kw_or}) -is:retweet lang:en'


def _fetch_recent_tweets(player_name: str) -> list[dict[str, Any]]:
    """Search recent tweets mentioning player + injury keywords."""
    token = os.environ.get("TWITTER_BEARER_TOKEN", "")
    if not token:
        return []

    params = {
        "query": _build_query(player_name),
        "max_results": MAX_RESULTS_PER_QUERY,
        "tweet.fields": "author_id,created_at,text",
        "expansions": "author_id",
        "user.fields": "public_metrics,verified",
    }

    try:
        resp = requests.get(
            TWITTER_SEARCH_URL,
            headers=_bearer_header(),
            params=params,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        data = resp.json()
        tweets = data.get("data", [])
        users = {
            u["id"]: u
            for u in data.get("includes", {}).get("users", [])
        }
        # Attach user metadata to each tweet
        for tweet in tweets:
            tweet["_user"] = users.get(tweet.get("author_id"), {})
        return tweets
    except requests.RequestException as exc:
        logger.warning("Twitter fetch failed for %s: %s", player_name, exc)
        return []


def _get_follower_count(user: dict[str, Any]) -> int:
    return user.get("public_metrics", {}).get("followers_count", 0)


def _keyword_in_text(text: str) -> str | None:
    """Return the first matched injury keyword or None."""
    lower = text.lower()
    for kw in INJURY_KEYWORDS:
        if kw.lower() in lower:
            return kw
    return None


# ---------------------------------------------------------------------------
# NBA official injury report
# ---------------------------------------------------------------------------

def _fetch_nba_official_injuries() -> list[dict[str, Any]]:
    """Pull from NBA stats injury data. Returns list of injury dicts."""
    try:
        resp = requests.get(
            NBA_INJURY_REPORT_URL,
            headers={"User-Agent": "EpochEngine/1.0"},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        return resp.json().get("resultSets", [])
    except requests.RequestException as exc:
        logger.warning("NBA official injury fetch failed: %s", exc)
        return []


def check_nba_official_injury(player_name: str) -> dict[str, Any] | None:
    """Check NBA official report for a player. Returns T1 signal or None."""
    result_sets = _fetch_nba_official_injuries()
    player_lower = player_name.lower()

    for rs in result_sets:
        headers = rs.get("headers", [])
        rows = rs.get("rowSet", [])
        for row in rows:
            row_dict = dict(zip(headers, row))
            name = str(row_dict.get("PLAYER_NAME", "")).lower()
            status = str(row_dict.get("GAME_STATUS_TEXT", ""))
            if player_lower in name and any(
                kw in status.lower() for kw in ["out", "doubtful", "dnr"]
            ):
                return _make_injury_signal(
                    player_name=player_name,
                    tier=TIER_1_CONFIDENCE,
                    source=TIER_1_SOURCE,
                    keyword_matched=status,
                    raw_text=f"NBA Official: {player_name} — {status}",
                    confidence_score=1.0,
                )
    return None


# ---------------------------------------------------------------------------
# Main detection entry point
# ---------------------------------------------------------------------------

def scan_for_injury(player_name: str) -> dict[str, Any] | None:
    """
    Full injury scan for a player. Returns highest-confidence signal found,
    or None if no signal detected.

    Priority: T1 (official) → T2 (beat reporter) → T3 (general mention)
    """
    # T1 — official NBA report
    official = check_nba_official_injury(player_name)
    if official:
        logger.info("T1 injury signal for %s via NBA official", player_name)
        return official

    # T2 / T3 — Twitter scan
    tweets = _fetch_recent_tweets(player_name)
    if not tweets:
        return None

    best_signal: dict[str, Any] | None = None
    best_tier = TIER_3_CONFIDENCE + 1  # start worse than T3

    for tweet in tweets:
        text = tweet.get("text", "")
        keyword = _keyword_in_text(text)
        if not keyword:
            continue

        user = tweet.get("_user", {})
        followers = _get_follower_count(user)
        verified = user.get("verified", False)

        if followers >= VERIFIED_FOLLOWER_THRESHOLD or verified:
            tier = TIER_2_CONFIDENCE
            source = TIER_2_SOURCE
            confidence = min(0.95, 0.70 + (followers / 1_000_000) * 0.25)
        else:
            tier = TIER_3_CONFIDENCE
            source = TIER_3_SOURCE
            confidence = 0.40

        if tier < best_tier:
            best_tier = tier
            best_signal = _make_injury_signal(
                player_name=player_name,
                tier=tier,
                source=source,
                keyword_matched=keyword,
                raw_text=text[:280],
                confidence_score=round(confidence, 3),
                source_followers=followers,
            )

    if best_signal:
        logger.info(
            "Injury signal for %s: tier=%d source=%s",
            player_name,
            best_signal["tier"],
            best_signal["source"],
        )
    return best_signal


def scan_active_roster(player_names: list[str]) -> list[dict[str, Any]]:
    """Scan multiple players. Returns all signals found, sorted by tier."""
    signals = []
    for name in player_names:
        signal = scan_for_injury(name)
        if signal:
            signals.append(signal)
        time.sleep(0.5)  # rate limit guard
    return sorted(signals, key=lambda s: s["tier"])


def is_high_confidence_injury(signal: dict[str, Any]) -> bool:
    """Return True if signal warrants immediate hot-swap (T1 or T2)."""
    return signal.get("tier", 99) <= TIER_2_CONFIDENCE
