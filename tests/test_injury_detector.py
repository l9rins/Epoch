"""
Tests — src/intelligence/injury_detector.py
SESSION B: Mid-Game Injury Hot-Swap
"""
from __future__ import annotations
from unittest.mock import patch, MagicMock
import time


class TestKeywordMatching:
    def test_keyword_in_text_matches_ruled_out(self):
        from src.intelligence.injury_detector import _keyword_in_text
        assert _keyword_in_text("Player ruled out for the rest of the game") == "ruled out"

    def test_keyword_in_text_matches_locker_room(self):
        from src.intelligence.injury_detector import _keyword_in_text
        assert _keyword_in_text("Star heading to locker room early") == "locker room"

    def test_keyword_in_text_matches_limping(self):
        from src.intelligence.injury_detector import _keyword_in_text
        assert _keyword_in_text("He is limping badly off the court") == "limping"

    def test_keyword_in_text_matches_dnr(self):
        from src.intelligence.injury_detector import _keyword_in_text
        assert _keyword_in_text("DNR confirmed by team") == "DNR"

    def test_keyword_in_text_no_match(self):
        from src.intelligence.injury_detector import _keyword_in_text
        assert _keyword_in_text("Great dunk by Tatum") is None

    def test_keyword_case_insensitive(self):
        from src.intelligence.injury_detector import _keyword_in_text
        assert _keyword_in_text("RULED OUT tonight") == "ruled out"


class TestBuildQuery:
    def test_query_contains_player_name(self):
        from src.intelligence.injury_detector import _build_query
        q = _build_query("Jayson Tatum")
        assert "Jayson Tatum" in q

    def test_query_contains_injury_keywords(self):
        from src.intelligence.injury_detector import _build_query
        q = _build_query("LeBron James")
        assert "ruled out" in q or "locker room" in q

    def test_query_excludes_retweets(self):
        from src.intelligence.injury_detector import _build_query
        q = _build_query("Stephen Curry")
        assert "-is:retweet" in q


class TestFollowerCount:
    def test_returns_zero_for_empty_user(self):
        from src.intelligence.injury_detector import _get_follower_count
        assert _get_follower_count({}) == 0

    def test_returns_correct_count(self):
        from src.intelligence.injury_detector import _get_follower_count
        user = {"public_metrics": {"followers_count": 125_000}}
        assert _get_follower_count(user) == 125_000


class TestMakeInjurySignal:
    def test_signal_has_required_keys(self):
        from src.intelligence.injury_detector import _make_injury_signal
        sig = _make_injury_signal(
            player_name="Tatum",
            tier=2,
            source="beat_reporter",
            keyword_matched="ruled out",
            raw_text="Tatum ruled out",
            confidence_score=0.85,
        )
        required = {
            "player_name", "tier", "source", "keyword_matched",
            "raw_text", "confidence_score", "detected_at_ts",
        }
        assert required.issubset(set(sig.keys()))

    def test_tier_preserved(self):
        from src.intelligence.injury_detector import _make_injury_signal
        sig = _make_injury_signal("P", 1, "nba_official", "out", "text", 1.0)
        assert sig["tier"] == 1

    def test_timestamp_is_recent(self):
        from src.intelligence.injury_detector import _make_injury_signal
        sig = _make_injury_signal("P", 3, "general_mention", "limping", "text", 0.4)
        assert abs(sig["detected_at_ts"] - time.time()) < 2.0


class TestIsHighConfidenceInjury:
    def test_tier1_is_high_confidence(self):
        from src.intelligence.injury_detector import is_high_confidence_injury
        assert is_high_confidence_injury({"tier": 1}) is True

    def test_tier2_is_high_confidence(self):
        from src.intelligence.injury_detector import is_high_confidence_injury
        assert is_high_confidence_injury({"tier": 2}) is True

    def test_tier3_is_not_high_confidence(self):
        from src.intelligence.injury_detector import is_high_confidence_injury
        assert is_high_confidence_injury({"tier": 3}) is False

    def test_missing_tier_is_not_high_confidence(self):
        from src.intelligence.injury_detector import is_high_confidence_injury
        assert is_high_confidence_injury({}) is False


class TestFetchRecentTweets:
    def test_returns_empty_without_token(self):
        from src.intelligence.injury_detector import _fetch_recent_tweets
        with patch.dict("os.environ", {}, clear=True):
            result = _fetch_recent_tweets("Jayson Tatum")
        assert result == []

    def test_returns_empty_on_request_failure(self):
        import requests
        from src.intelligence.injury_detector import _fetch_recent_tweets
        with patch.dict("os.environ", {"TWITTER_BEARER_TOKEN": "fake"}):
            with patch("requests.get", side_effect=requests.RequestException("fail")):
                result = _fetch_recent_tweets("LeBron James")
        assert result == []

    def test_parses_tweets_and_attaches_user(self):
        from src.intelligence.injury_detector import _fetch_recent_tweets
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "data": [{"author_id": "u1", "text": "Tatum ruled out", "id": "t1"}],
            "includes": {
                "users": [{"id": "u1", "public_metrics": {"followers_count": 80_000}}]
            },
        }
        with patch.dict("os.environ", {"TWITTER_BEARER_TOKEN": "fake"}):
            with patch("requests.get", return_value=mock_resp):
                tweets = _fetch_recent_tweets("Tatum")
        assert len(tweets) == 1
        assert tweets[0]["_user"]["public_metrics"]["followers_count"] == 80_000


class TestScanForInjury:
    def test_returns_none_when_no_signal(self):
        from src.intelligence.injury_detector import scan_for_injury
        with patch("src.intelligence.injury_detector.check_nba_official_injury", return_value=None):
            with patch("src.intelligence.injury_detector._fetch_recent_tweets", return_value=[]):
                result = scan_for_injury("Generic Player")
        assert result is None

    def test_t1_takes_priority_over_twitter(self):
        from src.intelligence.injury_detector import scan_for_injury, _make_injury_signal
        t1_signal = _make_injury_signal("Tatum", 1, "nba_official", "out", "official", 1.0)
        with patch("src.intelligence.injury_detector.check_nba_official_injury", return_value=t1_signal):
            result = scan_for_injury("Tatum")
        assert result["tier"] == 1
        assert result["source"] == "nba_official"

    def test_beat_reporter_returns_t2(self):
        from src.intelligence.injury_detector import scan_for_injury
        tweet = {
            "text": "Tatum ruled out, heading to locker room",
            "author_id": "u1",
            "_user": {"public_metrics": {"followers_count": 120_000}, "verified": False},
        }
        with patch("src.intelligence.injury_detector.check_nba_official_injury", return_value=None):
            with patch("src.intelligence.injury_detector._fetch_recent_tweets", return_value=[tweet]):
                result = scan_for_injury("Tatum")
        assert result is not None
        assert result["tier"] == 2

    def test_low_follower_returns_t3(self):
        from src.intelligence.injury_detector import scan_for_injury
        tweet = {
            "text": "Tatum is limping off the court",
            "author_id": "u2",
            "_user": {"public_metrics": {"followers_count": 1_000}, "verified": False},
        }
        with patch("src.intelligence.injury_detector.check_nba_official_injury", return_value=None):
            with patch("src.intelligence.injury_detector._fetch_recent_tweets", return_value=[tweet]):
                result = scan_for_injury("Tatum")
        assert result is not None
        assert result["tier"] == 3


class TestConstants:
    def test_verified_follower_threshold(self):
        from src.intelligence.injury_detector import VERIFIED_FOLLOWER_THRESHOLD
        assert VERIFIED_FOLLOWER_THRESHOLD == 50_000

    def test_tier_values(self):
        from src.intelligence.injury_detector import (
            TIER_1_CONFIDENCE, TIER_2_CONFIDENCE, TIER_3_CONFIDENCE
        )
        assert TIER_1_CONFIDENCE == 1
        assert TIER_2_CONFIDENCE == 2
        assert TIER_3_CONFIDENCE == 3
