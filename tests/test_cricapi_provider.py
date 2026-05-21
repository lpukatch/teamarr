"""Tests for CricAPI provider and client.

Verifies data normalization from CricAPI JSON responses to teamarr types,
status mapping, team ID derivation, series ID auto-detection, and caching.
"""

from datetime import UTC, date, datetime

from unittest.mock import MagicMock, patch

import pytest

from teamarr.core import LeagueMapping
from teamarr.providers.cricapi.client import CricAPIClient
from teamarr.providers.cricapi.provider import CricAPIProvider


# =============================================================================
# Fixtures
# =============================================================================


def _make_mapping(
    league_code: str = "ipl",
    provider_league_id: str = "test-series-guid-123",
    sport: str = "cricket",
    display_name: str = "Indian Premier League",
) -> LeagueMapping:
    return LeagueMapping(
        league_code=league_code,
        provider="cricapi",
        provider_league_id=provider_league_id,
        provider_league_name=None,
        sport=sport,
        display_name=display_name,
    )


def _make_mock_source(mapping: LeagueMapping | None = None):
    """Create a mock LeagueMappingSource."""
    source = MagicMock()
    if mapping is None:
        mapping = _make_mapping()

    source.get_mapping.return_value = mapping
    source.supports_league.return_value = mapping is not None
    source.get_leagues_for_provider.return_value = [mapping] if mapping else []
    return source


SAMPLE_SERIES_INFO_RESPONSE = {
    "status": "success",
    "data": {
        "info": {
            "id": "series-guid-abc",
            "name": "Indian Premier League 2026",
            "t20": 70,
            "matches": 74,
        },
        "matchList": [
            {
                "id": "match-guid-1",
                "name": "Chennai Super Kings vs Kolkata Knight Riders, 25th Match",
                "matchType": "t20",
                "status": "Match not started",
                "venue": "Wankhede Stadium, Mumbai",
                "date": "2026-03-26",
                "dateTimeGMT": "2026-03-26T14:00:00",
                "teams": ["Chennai Super Kings", "Kolkata Knight Riders"],
                "teamInfo": [
                    {
                        "name": "Chennai Super Kings",
                        "shortname": "CSK",
                        "img": "https://example.com/csk.png",
                    },
                    {
                        "name": "Kolkata Knight Riders",
                        "shortname": "KKR",
                        "img": "https://example.com/kkr.png",
                    },
                ],
                "matchStarted": False,
                "matchEnded": False,
            },
            {
                "id": "match-guid-2",
                "name": "Mumbai Indians vs Royal Challengers Bengaluru, 26th Match",
                "matchType": "t20",
                "status": "Kolkata Knight Riders won by 5 wickets",
                "venue": "M Chinnaswamy Stadium, Bengaluru",
                "date": "2026-03-27",
                "dateTimeGMT": "2026-03-27T10:00:00",
                "teams": ["Mumbai Indians", "Royal Challengers Bengaluru"],
                "teamInfo": [
                    {
                        "name": "Mumbai Indians",
                        "shortname": "MI",
                        "img": "https://example.com/mi.png",
                    },
                    {
                        "name": "Royal Challengers Bengaluru",
                        "shortname": "RCB",
                        "img": "https://example.com/rcb.png",
                    },
                ],
                "matchStarted": True,
                "matchEnded": True,
            },
        ],
    },
    "info": {"hitsToday": 3, "hitsLimit": 100, "totalRows": 74, "queryTime": 10},
}

SAMPLE_SERIES_SEARCH_RESPONSE = {
    "status": "success",
    "data": [
        {
            "id": "series-guid-2025",
            "name": "Indian Premier League 2025",
            "startDate": "2025-03-20",
            "endDate": "2025-05-25",
            "matches": 70,
        },
        {
            "id": "series-guid-2026",
            "name": "Indian Premier League 2026",
            "startDate": "2026-03-20",
            "endDate": "2026-05-25",
            "matches": 74,
        },
    ],
    "info": {"hitsToday": 5, "hitsLimit": 100},
}


# =============================================================================
# Client Tests
# =============================================================================


class TestCricAPIClient:
    """Tests for CricAPIClient."""

    def test_no_api_key_returns_none(self):
        """Client without API key returns None from requests."""
        client = CricAPIClient(api_key=None)
        result = client._request("series_info", {"id": "test"})
        assert result is None

    def test_rate_limit_tracking(self):
        """Client tracks hitsToday and hitsLimit from responses."""
        client = CricAPIClient(api_key="test-key")

        # Simulate updating rate limit info from a response
        client._update_rate_limit_info(SAMPLE_SERIES_INFO_RESPONSE)

        assert client.hits_today == 3
        assert client.hits_limit == 100
        assert client.hits_remaining == 97

    def test_rate_limit_none_response(self):
        """Client handles None response gracefully."""
        client = CricAPIClient(api_key="test-key")
        client._update_rate_limit_info(None)
        assert client.hits_today == 0
        assert client.hits_limit == 100

    def test_rate_limit_no_info_field(self):
        """Client handles response without info field."""
        client = CricAPIClient(api_key="test-key")
        client._update_rate_limit_info({"status": "success", "data": {}})
        assert client.hits_today == 0

    def test_supports_league(self):
        """Client delegates supports_league to mapping source."""
        source = _make_mock_source()
        client = CricAPIClient(league_mapping_source=source, api_key="key")

        assert client.supports_league("ipl") is True
        source.supports_league.assert_called_with("ipl", "cricapi")

    def test_supports_league_no_source(self):
        """Client returns False when no mapping source configured."""
        client = CricAPIClient(api_key="key")
        assert client.supports_league("ipl") is False

    def test_get_provider_league_id(self):
        """Client returns provider_league_id from mapping."""
        source = _make_mock_source()
        client = CricAPIClient(league_mapping_source=source, api_key="key")

        assert client.get_provider_league_id("ipl") == "test-series-guid-123"

    def test_get_provider_league_id_no_mapping(self):
        """Client returns None when mapping not found."""
        source = _make_mock_source()
        source.get_mapping.return_value = None
        client = CricAPIClient(league_mapping_source=source, api_key="key")

        assert client.get_provider_league_id("unknown") is None

    def test_get_sport(self):
        """Client returns sport from mapping."""
        source = _make_mock_source()
        client = CricAPIClient(league_mapping_source=source, api_key="key")

        assert client.get_sport("ipl") == "cricket"

    def test_get_sport_default(self):
        """Client returns 'cricket' when no mapping source."""
        client = CricAPIClient(api_key="key")
        assert client.get_sport("ipl") == "cricket"

    def test_thread_safe_client_creation(self):
        """Client creates httpx.Client lazily and thread-safely."""
        client = CricAPIClient(api_key="key")
        assert client._client is None

        httpx_client = client._get_client()
        assert httpx_client is not None

        # Second call returns same instance
        assert client._get_client() is httpx_client

    def test_cache_stats(self):
        """Client exposes cache statistics."""
        client = CricAPIClient(api_key="key")
        stats = client.cache_stats()
        assert "total_entries" in stats
        assert "hits" in stats

    def test_close_client(self):
        """Client closes underlying httpx.Client."""
        client = CricAPIClient(api_key="key")
        client._get_client()  # Force creation
        assert client._client is not None

        client.close()
        assert client._client is None

    def test_rate_limit_stats(self):
        """Client exposes rate limit statistics."""
        client = CricAPIClient(api_key="key")
        stats = client.rate_limit_stats()
        assert stats["hits_today"] == 0
        assert stats["hits_limit"] == 100
        assert stats["hits_remaining"] == 100


# =============================================================================
# Provider Tests
# =============================================================================


class TestCricAPIProviderProperties:
    """Tests for provider basic properties."""

    def test_name(self):
        source = _make_mock_source()
        provider = CricAPIProvider(league_mapping_source=source, api_key="key")
        assert provider.name == "cricapi"

    def test_supports_league(self):
        source = _make_mock_source()
        provider = CricAPIProvider(league_mapping_source=source, api_key="key")
        assert provider.supports_league("ipl") is True

    def test_get_supported_leagues(self):
        source = _make_mock_source()
        provider = CricAPIProvider(league_mapping_source=source, api_key="key")
        leagues = provider.get_supported_leagues()
        assert "ipl" in leagues


# =============================================================================
# Status Mapping Tests
# =============================================================================


class TestStatusMapping:
    """Tests for CricAPI status string to teamarr EventStatus mapping."""

    def _make_provider(self):
        source = _make_mock_source()
        return CricAPIProvider(league_mapping_source=source, api_key="key")

    def test_not_started(self):
        p = self._make_provider()
        status = p._parse_status({"status": "Match not started"})
        assert status.state == "scheduled"
        assert status.detail == "Match not started"

    def test_match_starts_at(self):
        p = self._make_provider()
        status = p._parse_status({"status": "Match starts at 14:00 GMT"})
        assert status.state == "scheduled"

    def test_won_by(self):
        p = self._make_provider()
        status = p._parse_status({"status": "Chennai Super Kings won by 5 wickets"})
        assert status.state == "final"
        assert status.detail == "Chennai Super Kings won by 5 wickets"

    def test_match_ended(self):
        p = self._make_provider()
        status = p._parse_status({"status": "Match ended"})
        assert status.state == "final"

    def test_postponed(self):
        p = self._make_provider()
        status = p._parse_status({"status": "Postponed due to rain"})
        assert status.state == "postponed"

    def test_cancelled(self):
        p = self._make_provider()
        status = p._parse_status({"status": "Cancelled"})
        assert status.state == "cancelled"

    def test_live_from_flags(self):
        p = self._make_provider()
        status = p._parse_status({
            "status": "",
            "matchStarted": True,
            "matchEnded": False,
        })
        assert status.state == "live"

    def test_default_scheduled(self):
        p = self._make_provider()
        status = p._parse_status({"status": ""})
        assert status.state == "scheduled"

    def test_empty_status_no_flags(self):
        p = self._make_provider()
        status = p._parse_status({})
        assert status.state == "scheduled"


# =============================================================================
# Datetime Parsing Tests
# =============================================================================


class TestDatetimeParsing:
    """Tests for CricAPI datetime string to UTC datetime parsing."""

    def _make_provider(self):
        source = _make_mock_source()
        return CricAPIProvider(league_mapping_source=source, api_key="key")

    def test_datetime_gmt(self):
        p = self._make_provider()
        dt = p._parse_datetime("2026-03-26T14:00:00", None)
        assert dt is not None
        assert dt.year == 2026
        assert dt.month == 3
        assert dt.day == 26
        assert dt.hour == 14
        assert dt.minute == 0
        assert dt.tzinfo is not None

    def test_date_only(self):
        p = self._make_provider()
        dt = p._parse_datetime(None, "2026-03-26")
        assert dt is not None
        assert dt.year == 2026
        assert dt.month == 3
        assert dt.day == 26
        assert dt.hour == 0

    def test_prefers_datetime_gmt(self):
        p = self._make_provider()
        dt = p._parse_datetime("2026-03-26T14:00:00", "2026-03-27")
        assert dt is not None
        assert dt.day == 26  # Uses dateTimeGMT, not date

    def test_none_both(self):
        p = self._make_provider()
        dt = p._parse_datetime(None, None)
        assert dt is None


# =============================================================================
# Team ID Derivation Tests
# =============================================================================


class TestTeamIdDerivation:
    """Tests for team ID generation from team names."""

    def _make_provider(self):
        source = _make_mock_source()
        return CricAPIProvider(league_mapping_source=source, api_key="key")

    def test_simple_name(self):
        p = self._make_provider()
        team_id = p._make_team_id("Chennai Super Kings")
        assert team_id == "cricapi_chennai_super_kings"

    def test_empty_name(self):
        p = self._make_provider()
        team_id = p._make_team_id("")
        assert team_id == ""

    def test_special_characters(self):
        p = self._make_provider()
        team_id = p._make_team_id("St. Lucia Zoups FC")
        assert team_id == "cricapi_st_lucia_zoups_fc"

    def test_team_ids_match(self):
        p = self._make_provider()
        team_id = p._make_team_id("Chennai Super Kings")
        assert p._team_ids_match(team_id, "Chennai Super Kings") is True

    def test_team_ids_no_match(self):
        p = self._make_provider()
        team_id = p._make_team_id("Chennai Super Kings")
        assert p._team_ids_match(team_id, "Mumbai Indians") is False


# =============================================================================
# Abbreviation Generation Tests
# =============================================================================


class TestAbbreviation:
    """Tests for abbreviation generation from team names."""

    def _make_provider(self):
        source = _make_mock_source()
        return CricAPIProvider(league_mapping_source=source, api_key="key")

    def test_multi_word(self):
        p = self._make_provider()
        abbrev = p._make_abbrev("Chennai Super Kings")
        assert abbrev == "CSK"

    def test_empty(self):
        p = self._make_provider()
        abbrev = p._make_abbrev("")
        assert abbrev == ""

    def test_filters_stopwords(self):
        p = self._make_provider()
        abbrev = p._make_abbrev("The Club of FC")
        # "The", "of", "FC", "club" are all skipped -> empty -> fallback to first 3 chars
        assert abbrev == "THE"

    def test_cap_at_four(self):
        p = self._make_provider()
        abbrev = p._make_abbrev("One Two Three Four Five")
        assert len(abbrev) <= 4


# =============================================================================
# Match Parsing Tests
# =============================================================================


class TestMatchParsing:
    """Tests for full match data parsing into Event dataclass."""

    def _make_provider_with_mock_client(self):
        source = _make_mock_source()
        client = CricAPIClient(league_mapping_source=source, api_key="test-key")
        provider = CricAPIProvider(
            league_mapping_source=source,
            client=client,
            api_key="test-key",
        )
        return provider

    def test_parse_match_basic(self):
        p = self._make_provider_with_mock_client()
        match_data = SAMPLE_SERIES_INFO_RESPONSE["data"]["matchList"][0]

        event = p._parse_match(match_data, "ipl")

        assert event is not None
        assert event.id == "match-guid-1"
        assert event.provider == "cricapi"
        assert event.name == "Chennai Super Kings vs Kolkata Knight Riders, 25th Match"
        assert event.league == "ipl"
        assert event.sport == "cricket"
        assert event.status.state == "scheduled"

        # Team names
        assert event.home_team.name == "Chennai Super Kings"
        assert event.away_team.name == "Kolkata Knight Riders"

        # Short names from teamInfo
        assert event.home_team.short_name == "CSK"
        assert event.away_team.short_name == "KKR"

        # Abbreviations from teamInfo
        assert event.home_team.abbreviation == "CSK"
        assert event.away_team.abbreviation == "KKR"

        # Start time
        assert event.start_time.year == 2026
        assert event.start_time.month == 3
        assert event.start_time.day == 26
        assert event.start_time.hour == 14

        # Venue
        assert event.venue is not None
        assert event.venue.name == "Wankhede Stadium"
        assert event.venue.city == "Mumbai"

    def test_parse_match_final_status(self):
        p = self._make_provider_with_mock_client()
        match_data = SAMPLE_SERIES_INFO_RESPONSE["data"]["matchList"][1]

        event = p._parse_match(match_data, "ipl")
        assert event is not None
        assert event.status.state == "final"
        assert "won by" in event.status.detail.lower()

    def test_parse_match_no_id(self):
        p = self._make_provider_with_mock_client()
        event = p._parse_match({}, "ipl")
        assert event is None

    def test_parse_match_no_datetime(self):
        p = self._make_provider_with_mock_client()
        event = p._parse_match({"id": "test-id"}, "ipl")
        assert event is None


# =============================================================================
# Venue Parsing Tests
# =============================================================================


class TestVenueParsing:
    """Tests for venue string parsing."""

    def _make_provider(self):
        source = _make_mock_source()
        return CricAPIProvider(league_mapping_source=source, api_key="key")

    def test_venue_with_city(self):
        p = self._make_provider()
        venue = p._parse_venue("Wankhede Stadium, Mumbai")
        assert venue is not None
        assert venue.name == "Wankhede Stadium"
        assert venue.city == "Mumbai"

    def test_venue_without_city(self):
        p = self._make_provider()
        venue = p._parse_venue("Melbourne Cricket Ground")
        assert venue is not None
        assert venue.name == "Melbourne Cricket Ground"
        assert venue.city is None

    def test_venue_empty(self):
        p = self._make_provider()
        venue = p._parse_venue("")
        assert venue is None

    def test_venue_none(self):
        p = self._make_provider()
        venue = p._parse_venue(None)
        assert venue is None


# =============================================================================
# Integration Tests (with mocked client)
# =============================================================================


class TestGetEvents:
    """Tests for get_events using mocked series_info responses."""

    def _make_provider_with_mocked_client(self):
        source = _make_mock_source()
        client = MagicMock(spec=CricAPIClient)
        client.supports_league.return_value = True
        client.get_provider_league_id.return_value = "series-guid-abc"
        client.get_sport.return_value = "cricket"
        client.get_series_info.return_value = SAMPLE_SERIES_INFO_RESPONSE

        provider = CricAPIProvider(
            league_mapping_source=source,
            client=client,
            api_key="test-key",
        )
        return provider, client

    def test_get_events_filters_by_date(self):
        provider, _ = self._make_provider_with_mocked_client()

        events = provider.get_events("ipl", date(2026, 3, 26))
        assert len(events) == 1
        assert events[0].id == "match-guid-1"

    def test_get_events_no_matches_for_date(self):
        provider, _ = self._make_provider_with_mocked_client()

        events = provider.get_events("ipl", date(2026, 4, 1))
        assert events == []

    def test_get_events_multiple_on_same_day(self):
        provider, client = self._make_provider_with_mocked_client()

        # Add another match on the same date
        response = {
            "status": "success",
            "data": {
                "info": {"id": "s1", "name": "Test", "matches": 2},
                "matchList": [
                    {
                        "id": "m1",
                        "name": "Team A vs Team B",
                        "matchType": "t20",
                        "status": "Match not started",
                        "venue": "Ground 1",
                        "date": "2026-04-01",
                        "dateTimeGMT": "2026-04-01T10:00:00",
                        "teams": ["Team A", "Team B"],
                        "teamInfo": [
                            {"name": "Team A", "shortname": "TA"},
                            {"name": "Team B", "shortname": "TB"},
                        ],
                        "matchStarted": False,
                        "matchEnded": False,
                    },
                    {
                        "id": "m2",
                        "name": "Team C vs Team D",
                        "matchType": "t20",
                        "status": "Match not started",
                        "venue": "Ground 2",
                        "date": "2026-04-01",
                        "dateTimeGMT": "2026-04-01T14:00:00",
                        "teams": ["Team C", "Team D"],
                        "teamInfo": [
                            {"name": "Team C", "shortname": "TC"},
                            {"name": "Team D", "shortname": "TD"},
                        ],
                        "matchStarted": False,
                        "matchEnded": False,
                    },
                ],
            },
        }
        client.get_series_info.return_value = response

        events = provider.get_events("ipl", date(2026, 4, 1))
        assert len(events) == 2


class TestGetTeamSchedule:
    """Tests for get_team_schedule."""

    def _make_provider_with_mocked_client(self):
        source = _make_mock_source()
        client = MagicMock(spec=CricAPIClient)
        client.supports_league.return_value = True
        client.get_provider_league_id.return_value = "series-guid-abc"
        client.get_sport.return_value = "cricket"
        client.get_series_info.return_value = SAMPLE_SERIES_INFO_RESPONSE

        provider = CricAPIProvider(
            league_mapping_source=source,
            client=client,
            api_key="test-key",
        )
        return provider

    def test_get_team_schedule_filters_by_team(self):
        provider = self._make_provider_with_mocked_client()

        team_id = "cricapi_chennai_super_kings"
        with patch(
            "teamarr.providers.cricapi.provider.date"
        ) as mock_date:
            mock_date.today.return_value = date(2026, 3, 25)
            mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
            mock_date.fromisoformat = date.fromisoformat
            events = provider.get_team_schedule(team_id, "ipl", days_ahead=30)
        assert len(events) == 1
        assert events[0].id == "match-guid-1"

    def test_get_team_schedule_no_matches(self):
        provider = self._make_provider_with_mocked_client()

        team_id = "cricapi_nonexistent_team"
        events = provider.get_team_schedule(team_id, "ipl", days_ahead=30)
        assert events == []


class TestGetLeagueTeams:
    """Tests for get_league_teams."""

    def _make_provider_with_mocked_client(self):
        source = _make_mock_source()
        client = MagicMock(spec=CricAPIClient)
        client.supports_league.return_value = True
        client.get_provider_league_id.return_value = "series-guid-abc"
        client.get_sport.return_value = "cricket"
        client.get_series_info.return_value = SAMPLE_SERIES_INFO_RESPONSE

        provider = CricAPIProvider(
            league_mapping_source=source,
            client=client,
            api_key="test-key",
        )
        return provider

    def test_get_league_teams_extracts_unique(self):
        provider = self._make_provider_with_mocked_client()

        teams = provider.get_league_teams("ipl")
        assert len(teams) == 4  # CSK, KKR, MI, RCB

        team_names = {t.name for t in teams}
        assert "Chennai Super Kings" in team_names
        assert "Kolkata Knight Riders" in team_names
        assert "Mumbai Indians" in team_names
        assert "Royal Challengers Bengaluru" in team_names

    def test_get_league_teams_has_logos(self):
        provider = self._make_provider_with_mocked_client()

        teams = provider.get_league_teams("ipl")
        csk = next(t for t in teams if "Chennai" in t.name)
        assert csk.logo_url == "https://example.com/csk.png"


class TestSeriesAutoDetection:
    """Tests for auto-detection of series ID."""

    def _make_provider_with_mocked_client(self):
        source = _make_mock_source()
        client = MagicMock(spec=CricAPIClient)
        client.supports_league.return_value = True
        client.get_sport.return_value = "cricket"
        client.get_series_info.return_value = SAMPLE_SERIES_INFO_RESPONSE
        client.search_series.return_value = SAMPLE_SERIES_SEARCH_RESPONSE

        # Initially no provider_league_id set
        client.get_provider_league_id.return_value = None

        updater = MagicMock()
        provider = CricAPIProvider(
            league_mapping_source=source,
            client=client,
            api_key="test-key",
            series_id_updater=updater,
        )
        return provider, client, updater

    def test_auto_detect_picks_latest_series(self):
        provider, client, updater = self._make_provider_with_mocked_client()

        events = provider.get_events("ipl", date(2026, 3, 26))
        assert len(events) == 1

        # Should have called search_series with "Indian Premier League"
        client.search_series.assert_called_once()
        search_arg = client.search_series.call_args[0][0]
        assert "Indian Premier League" in search_arg

        # Should have called updater to persist the new series ID
        updater.assert_called_once_with("ipl", "series-guid-2026")

    def test_auto_detect_skips_zero_match_series(self):
        provider, client, updater = self._make_provider_with_mocked_client()

        # Return search results where one series has 0 matches
        client.search_series.return_value = {
            "status": "success",
            "data": [
                {
                    "id": "old-series",
                    "name": "IPL 2024",
                    "startDate": "2024-03-20",
                    "matches": 0,  # No matches
                },
                {
                    "id": "good-series",
                    "name": "IPL 2026",
                    "startDate": "2026-03-20",
                    "matches": 70,
                },
            ],
        }

        provider.get_events("ipl", date(2026, 3, 26))

        # Should skip the 0-match series and pick the good one
        updater.assert_called_once_with("ipl", "good-series")

    def test_auto_detect_no_search_term(self):
        """Provider with unknown league code and no display name returns empty."""
        source = _make_mock_source(
            _make_mapping(league_code="unknown_cricket", display_name="")
        )
        client = MagicMock(spec=CricAPIClient)
        client.get_provider_league_id.return_value = None
        client.supports_league.return_value = True
        client.get_sport.return_value = "cricket"

        provider = CricAPIProvider(
            league_mapping_source=source,
            client=client,
            api_key="test-key",
        )

        events = provider.get_events("unknown_cricket", date(2026, 3, 26))
        assert events == []

    def test_stale_series_id_triggers_auto_detect(self):
        """When provider_league_id returns an error/failure status, auto-detect."""
        provider, client, updater = self._make_provider_with_mocked_client()

        # Set a stale series ID that returns a failure status
        client.get_provider_league_id.return_value = "stale-series-id"
        failure_response = {
            "status": "failure",
            "reason": "Series not found",
        }
        client.get_series_info.side_effect = [
            failure_response,  # First call with stale ID
            SAMPLE_SERIES_INFO_RESPONSE,  # Second call after auto-detect
        ]

        events = provider.get_events("ipl", date(2026, 3, 26))
        assert len(events) == 1

        # Should have called search and updater
        client.search_series.assert_called_once()
        updater.assert_called_once()

    def test_empty_matchlist_does_not_trigger_auto_detect(self):
        """A valid series with an empty matchList (off-season) is returned as-is."""
        provider, client, updater = self._make_provider_with_mocked_client()

        client.get_provider_league_id.return_value = "current-series-id"
        off_season_response = {
            "status": "success",
            "data": {
                "info": {"id": "current-series-id", "name": "IPL 2026", "matches": 0},
                "matchList": [],
            },
        }
        client.get_series_info.return_value = off_season_response

        events = provider.get_events("ipl", date(2026, 3, 26))
        assert events == []

        # Should NOT have called search or updater — no API waste
        client.search_series.assert_not_called()
        updater.assert_not_called()


class TestGetEvent:
    """Tests for get_event (single match lookup)."""

    def test_get_event_returns_match(self):
        source = _make_mock_source()
        client = MagicMock(spec=CricAPIClient)
        client.get_sport.return_value = "cricket"

        match_response = {
            "status": "success",
            "data": SAMPLE_SERIES_INFO_RESPONSE["data"]["matchList"][0],
        }
        client.get_match_info.return_value = match_response

        provider = CricAPIProvider(
            league_mapping_source=source,
            client=client,
            api_key="test-key",
        )

        event = provider.get_event("match-guid-1", "ipl")
        assert event is not None
        assert event.id == "match-guid-1"

    def test_get_event_not_found(self):
        source = _make_mock_source()
        client = MagicMock(spec=CricAPIClient)
        client.get_match_info.return_value = None

        provider = CricAPIProvider(
            league_mapping_source=source,
            client=client,
            api_key="test-key",
        )

        event = provider.get_event("nonexistent", "ipl")
        assert event is None


class TestGetTeam:
    """Tests for get_team."""

    def test_get_team_by_name(self):
        source = _make_mock_source()
        client = MagicMock(spec=CricAPIClient)
        client.supports_league.return_value = True
        client.get_provider_league_id.return_value = "series-guid-abc"
        client.get_sport.return_value = "cricket"
        client.get_series_info.return_value = SAMPLE_SERIES_INFO_RESPONSE

        provider = CricAPIProvider(
            league_mapping_source=source,
            client=client,
            api_key="test-key",
        )

        team = provider.get_team("cricapi_chennai_super_kings", "ipl")
        assert team is not None
        assert team.name == "Chennai Super Kings"
        assert team.abbreviation == "CSK"
        assert team.logo_url == "https://example.com/csk.png"

    def test_get_team_not_found(self):
        source = _make_mock_source()
        client = MagicMock(spec=CricAPIClient)
        client.supports_league.return_value = True
        client.get_provider_league_id.return_value = "series-guid-abc"
        client.get_sport.return_value = "cricket"
        client.get_series_info.return_value = SAMPLE_SERIES_INFO_RESPONSE

        provider = CricAPIProvider(
            league_mapping_source=source,
            client=client,
            api_key="test-key",
        )

        team = provider.get_team("cricapi_nonexistent_team", "ipl")
        assert team is None


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_parse_match_missing_team_info(self):
        """Match with teams array but no teamInfo should still parse."""
        source = _make_mock_source()
        provider = CricAPIProvider(league_mapping_source=source, api_key="key")

        match_data = {
            "id": "m1",
            "name": "Team A vs Team B",
            "date": "2026-04-01",
            "dateTimeGMT": "2026-04-01T10:00:00",
            "teams": ["Team A", "Team B"],
            "teamInfo": [],  # Empty teamInfo
            "status": "Match not started",
            "matchStarted": False,
            "matchEnded": False,
        }

        event = provider._parse_match(match_data, "ipl")
        assert event is not None
        assert event.home_team.name == "Team A"
        assert event.away_team.name == "Team B"
        # Should derive IDs from names
        assert "team_a" in event.home_team.id
        assert "team_b" in event.away_team.id

    def test_parse_match_no_teams_at_all(self):
        """Match with no teams at all should still parse with empty team data."""
        source = _make_mock_source()
        provider = CricAPIProvider(league_mapping_source=source, api_key="key")

        match_data = {
            "id": "m1",
            "name": "TBD vs TBD",
            "date": "2026-04-01",
            "dateTimeGMT": "2026-04-01T10:00:00",
            "teams": [],
            "teamInfo": [],
            "status": "Match not started",
            "matchStarted": False,
            "matchEnded": False,
        }

        event = provider._parse_match(match_data, "ipl")
        assert event is not None
        # Short name should fall back to event name
        assert event.short_name == "TBD vs TBD"

    def test_provider_with_no_client(self):
        """Provider with no client or api_key creates client internally."""
        source = _make_mock_source()
        provider = CricAPIProvider(league_mapping_source=source)
        assert provider._client is not None
        assert provider._client.api_key is None

    def test_series_id_updater_error_doesnt_crash(self):
        """If series_id_updater raises, provider still returns data."""
        source = _make_mock_source()
        client = MagicMock(spec=CricAPIClient)
        client.get_provider_league_id.return_value = None
        client.supports_league.return_value = True
        client.get_sport.return_value = "cricket"
        client.search_series.return_value = SAMPLE_SERIES_SEARCH_RESPONSE
        client.get_series_info.return_value = SAMPLE_SERIES_INFO_RESPONSE

        failing_updater = MagicMock(side_effect=RuntimeError("DB error"))

        provider = CricAPIProvider(
            league_mapping_source=source,
            client=client,
            api_key="test-key",
            series_id_updater=failing_updater,
        )

        events = provider.get_events("ipl", date(2026, 3, 26))
        # Should still return events even if updater fails
        assert len(events) == 1
