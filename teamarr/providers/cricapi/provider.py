"""CricAPI sports data provider.

Fetches cricket fixture data from CricketData.org (CricAPI) and normalizes
it into teamarr's internal types. Used for cricket leagues (IPL, BBL, SA20, etc.).
"""

import logging
import re
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta

from teamarr.core import (
    Event,
    EventStatus,
    LeagueMappingSource,
    SportsProvider,
    Team,
    Venue,
)
from teamarr.providers.cricapi.client import CricAPIClient

logger = logging.getLogger(__name__)

# Type alias for series ID updater callback
# Takes (league_code, new_series_id) -> None
SeriesIdUpdater = Callable[[str, str], None]

# Mapping of league codes to CricAPI search terms for auto-detection
LEAGUE_SEARCH_TERMS: dict[str, str] = {
    "ipl": "Indian Premier League",
    "bbl": "Big Bash League",
    "sa20": "SA20",
}


class CricAPIProvider(SportsProvider):
    """CricAPI implementation of SportsProvider.

    Handles cricket leagues (IPL, BBL, SA20, etc.) using CricketData.org API.
    """

    def __init__(
        self,
        league_mapping_source: LeagueMappingSource | None = None,
        client: CricAPIClient | None = None,
        api_key: str | None = None,
        series_id_updater: SeriesIdUpdater | None = None,
    ):
        self._league_mapping_source = league_mapping_source
        self._client = client or CricAPIClient(
            league_mapping_source=league_mapping_source,
            api_key=api_key,
        )
        self._series_id_updater = series_id_updater

    @property
    def name(self) -> str:
        return "cricapi"

    def supports_league(self, league: str) -> bool:
        return self._client.supports_league(league)

    def get_events(self, league: str, target_date: date) -> list[Event]:
        """Get all events for a league on a specific date.

        Fetches series_info (all matches for the series) and filters by date.
        """
        series_data = self._get_series_matches(league)
        if not series_data:
            return []

        date_str = target_date.strftime("%Y-%m-%d")
        match_list = series_data.get("matchList", [])

        events = []
        for match in match_list:
            match_date = match.get("date", "")
            if match_date != date_str:
                continue
            event = self._parse_match(match, league)
            if event:
                events.append(event)

        return events

    def get_team_schedule(
        self,
        team_id: str,
        league: str,
        days_ahead: int = 14,
    ) -> list[Event]:
        """Get upcoming schedule for a specific team.

        Fetches series_info and filters by team name.
        Team IDs in CricAPI are derived from team names.
        """
        series_data = self._get_series_matches(league)
        if not series_data:
            return []

        match_list = series_data.get("matchList", [])
        today = date.today()
        cutoff = today + timedelta(days=days_ahead)

        events = []
        seen_ids: set[str] = set()

        for match in match_list:
            # Check team name match
            teams = match.get("teams", [])
            if not self._team_in_match(team_id, teams, match):
                continue

            # Filter by date range
            match_date_str = match.get("date", "")
            if not match_date_str:
                continue
            try:
                match_date = date.fromisoformat(match_date_str)
            except ValueError:
                continue

            if match_date < today or match_date > cutoff:
                continue

            event = self._parse_match(match, league)
            if event and event.id not in seen_ids:
                seen_ids.add(event.id)
                events.append(event)

        events.sort(key=lambda e: e.start_time)
        return events

    def get_team(self, team_id: str, league: str) -> Team | None:
        """Get team details.

        Extracts team info from series_info teamInfo array.
        Team ID is derived from team name.
        """
        series_data = self._get_series_matches(league)
        if not series_data:
            return None

        match_list = series_data.get("matchList", [])

        for match in match_list:
            team_info_list = match.get("teamInfo", [])
            for team_info in team_info_list:
                team_name = team_info.get("name", "")
                if self._team_ids_match(team_id, team_name):
                    return self._parse_team_info(team_info, league)

        return None

    def get_event(self, event_id: str, league: str) -> Event | None:
        """Get a specific event by ID.

        Fetches match_info for the event ID.
        """
        data = self._client.get_match_info(event_id)
        if not data:
            return None

        match_data = data.get("data")
        if not match_data:
            return None

        return self._parse_match(match_data, league)

    def get_league_teams(self, league: str) -> list[Team]:
        """Get all teams in a league.

        Extracts unique teams from series_info matchList.
        """
        series_data = self._get_series_matches(league)
        if not series_data:
            return []

        match_list = series_data.get("matchList", [])
        seen_teams: dict[str, dict] = {}  # name -> teamInfo dict

        for match in match_list:
            for team_info in match.get("teamInfo", []):
                name = team_info.get("name", "")
                if name and name not in seen_teams:
                    seen_teams[name] = team_info

        return [self._parse_team_info(info, league) for info in seen_teams.values()]

    def get_supported_leagues(self) -> list[str]:
        """Get all leagues this provider supports."""
        if not self._league_mapping_source:
            return []
        mappings = self._league_mapping_source.get_leagues_for_provider("cricapi")
        return [m.league_code for m in mappings]

    # =========================================================================
    # Series ID resolution
    # =========================================================================

    def _get_series_matches(self, league: str) -> dict | None:
        """Fetch all matches for a league's series.

        Attempts to resolve the series ID:
        1. Use provider_league_id if set and returns valid data
        2. Auto-detect via series search if the stored ID is invalid or stale

        A valid series with an empty matchList (off-season / rest day) is
        returned as-is rather than triggering a re-detect, to conserve API quota.
        """
        series_id = self._client.get_provider_league_id(league)

        if series_id:
            data = self._client.get_series_info(series_id)
            if data and data.get("status") == "success":
                return data.get("data")

            # Series ID returned an error or failure status — try auto-detect
            logger.info(
                "[CRAPI] Series ID %s returned invalid data for %s, auto-detecting",
                series_id,
                league,
            )

        return self._resolve_series_id(league)

    def _resolve_series_id(self, league: str) -> dict | None:
        """Auto-detect current series ID by searching.

        Searches for the series by name, picks the one with the latest
        startDate that has matches > 0. Persists new ID via callback.
        """
        search_term = LEAGUE_SEARCH_TERMS.get(league)
        if not search_term:
            # Try using the display name from league mapping
            if self._league_mapping_source:
                mapping = self._league_mapping_source.get_mapping(league, "cricapi")
                if mapping and mapping.display_name:
                    search_term = mapping.display_name
            if not search_term:
                logger.warning("[CRAPI] No search term mapping for league %s", league)
                return None

        search_result = self._client.search_series(search_term)
        if not search_result:
            logger.warning("[CRAPI] Series search returned no results for %s", search_term)
            return None

        series_list = search_result.get("data", [])
        if not series_list:
            logger.warning("[CRAPI] No series found for search term %s", search_term)
            return None

        # Pick series with latest startDate that has matches > 0
        best_series = None
        best_start = ""

        for series in series_list:
            matches_count = series.get("matches", 0)
            if not matches_count or int(matches_count) <= 0:
                continue

            start_date = series.get("startDate", "")
            if start_date and start_date > best_start:
                best_start = start_date
                best_series = series

        if not best_series:
            logger.warning("[CRAPI] No series with matches found for %s", search_term)
            return None

        series_id = best_series.get("id", "")
        series_name = best_series.get("name", "unknown")
        logger.info(
            "[CRAPI] Auto-detected series %s (%s) for league %s",
            series_id,
            series_name,
            league,
        )

        # Persist new series ID via callback
        if self._series_id_updater and series_id:
            try:
                self._series_id_updater(league, series_id)
                logger.info(
                    "[CRAPI] Updated series ID for %s to %s",
                    league,
                    series_id,
                )
            except Exception as e:
                logger.warning(
                    "[CRAPI] Failed to update series ID for %s: %s",
                    league,
                    e,
                )

        # Fetch the full series info with the detected ID
        data = self._client.get_series_info(series_id)
        if data and data.get("status") == "success":
            return data.get("data")

        return None

    # =========================================================================
    # Parsing helpers
    # =========================================================================

    def _parse_match(self, match_data: dict, league: str) -> Event | None:
        """Parse a CricAPI match dict into an Event dataclass."""
        try:
            match_id = match_data.get("id")
            if not match_id:
                return None

            # Parse start time
            start_time = self._parse_datetime(
                match_data.get("dateTimeGMT"),
                match_data.get("date"),
            )
            if not start_time:
                return None

            sport = self._client.get_sport(league)

            # Build teams
            teams = match_data.get("teams", [])
            team_info_list = match_data.get("teamInfo", [])

            home_team = self._build_team(
                teams[0] if len(teams) > 0 else "",
                team_info_list,
                0,
                league,
                sport,
                match_id,
            )
            away_team = self._build_team(
                teams[1] if len(teams) > 1 else "",
                team_info_list,
                1,
                league,
                sport,
                match_id,
            )

            # Parse status
            status = self._parse_status(match_data)

            # Parse venue
            venue = self._parse_venue(match_data.get("venue", ""))

            # Build names
            event_name = match_data.get("name", "")
            if not event_name and home_team.name and away_team.name:
                event_name = f"{home_team.name} vs {away_team.name}"

            short_name = ""
            if home_team.abbreviation and away_team.abbreviation:
                short_name = f"{away_team.abbreviation} vs {home_team.abbreviation}"
            elif home_team.short_name and away_team.short_name:
                short_name = f"{away_team.short_name} vs {home_team.short_name}"
            else:
                short_name = event_name

            return Event(
                id=str(match_id),
                provider=self.name,
                name=event_name,
                short_name=short_name,
                start_time=start_time,
                home_team=home_team,
                away_team=away_team,
                status=status,
                league=league,
                sport=sport,
                venue=venue,
            )

        except Exception as e:
            logger.warning(
                "[CRAPI] Failed to parse match %s: %s",
                match_data.get("id", "unknown"),
                e,
            )
            return None

    def _build_team(
        self,
        team_name: str,
        team_info_list: list[dict],
        index: int,
        league: str,
        sport: str,
        match_id: str,
    ) -> Team:
        """Build a Team dataclass from match data.

        Uses teamInfo if available for richer data (shortname, img).
        Falls back to teams array for basic name.
        """
        # Try to get teamInfo for this index
        team_info = None
        if index < len(team_info_list):
            info = team_info_list[index]
            info_name = info.get("name", "")
            if info_name == team_name:
                team_info = info

        # If no matching teamInfo by index, try by name
        if not team_info and team_name:
            for info in team_info_list:
                if info.get("name") == team_name:
                    team_info = info
                    break

        if team_info:
            return self._parse_team_info(team_info, league, sport)

        # Fallback: build from team name only
        team_id = self._make_team_id(team_name)
        abbrev = self._make_abbrev(team_name)

        return Team(
            id=team_id,
            provider=self.name,
            name=team_name,
            short_name=team_name,
            abbreviation=abbrev,
            league=league,
            sport=sport,
        )

    def _parse_team_info(
        self,
        team_info: dict,
        league: str,
        sport: str | None = None,
    ) -> Team:
        """Parse a teamInfo dict into a Team dataclass."""
        name = team_info.get("name", "")
        short_name = team_info.get("shortname", "") or name
        abbrev = team_info.get("shortname", "") or self._make_abbrev(name)
        logo_url = team_info.get("img")
        team_id = self._make_team_id(name)

        return Team(
            id=team_id,
            provider=self.name,
            name=name,
            short_name=short_name,
            abbreviation=abbrev,
            league=league,
            sport=sport or self._client.get_sport(league),
            logo_url=logo_url,
        )

    def _parse_status(self, match_data: dict) -> EventStatus:
        """Parse CricAPI match status into EventStatus.

        Status mapping:
        - Contains "not started" or "Match starts at" -> "scheduled"
        - Contains "won by" or "Match ended" -> "final"
        - Contains "Postponed" -> "postponed"
        - Contains "Cancelled" -> "cancelled"
        - Otherwise if matchStarted=True and matchEnded=False -> "live"
        """
        status_str = match_data.get("status", "")
        status_lower = status_str.lower() if status_str else ""

        if "not started" in status_lower or "match starts at" in status_lower:
            return EventStatus(state="scheduled", detail=status_str or None)

        if "won by" in status_lower or "match ended" in status_lower:
            return EventStatus(state="final", detail=status_str or None)

        if "postponed" in status_lower:
            return EventStatus(state="postponed", detail=status_str or None)

        if "cancelled" in status_lower:
            return EventStatus(state="cancelled", detail=status_str or None)

        # Check live status from boolean flags
        match_started = match_data.get("matchStarted", False)
        match_ended = match_data.get("matchEnded", False)

        if match_started and not match_ended:
            return EventStatus(state="live", detail=status_str or None)

        # Default to scheduled
        return EventStatus(state="scheduled", detail=status_str or None)

    def _parse_venue(self, venue_str: str) -> Venue | None:
        """Parse venue string from CricAPI.

        Venue format: "Stadium Name, City" or just "Stadium Name"
        """
        if not venue_str:
            return None

        # Try to split on last comma for city
        parts = venue_str.rsplit(",", 1)
        if len(parts) == 2:
            return Venue(
                name=parts[0].strip(),
                city=parts[1].strip(),
            )

        return Venue(name=venue_str.strip())

    def _parse_datetime(
        self,
        datetime_gmt: str | None,
        date_str: str | None,
    ) -> datetime | None:
        """Parse CricAPI datetime into UTC datetime.

        Prefers dateTimeGMT (ISO with explicit GMT).
        Falls back to date-only string (assumes midnight UTC).
        """
        if datetime_gmt:
            try:
                # CricAPI format: "2026-03-26T14:00:00" (already GMT/UTC)
                dt = datetime.fromisoformat(datetime_gmt)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=UTC)
                return dt
            except ValueError:
                pass

        if date_str:
            try:
                dt = datetime.fromisoformat(date_str)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=UTC)
                return dt
            except ValueError:
                pass

        return None

    def _make_team_id(self, team_name: str) -> str:
        """Derive a stable team ID from team name.

        CricAPI doesn't provide stable numeric IDs for teams,
        so we use a slug derived from the name.
        """
        if not team_name:
            return ""

        # Lowercase, replace non-alphanumeric with underscore, collapse multiples
        slug = re.sub(r"[^a-z0-9]+", "_", team_name.lower()).strip("_")
        return f"cricapi_{slug}"

    def _make_abbrev(self, team_name: str) -> str:
        """Generate abbreviation from team name.

        Takes first letters of significant words, up to 4 characters.
        """
        if not team_name:
            return ""

        words = team_name.split()
        # Filter out common filler words
        skip = {"the", "of", "and", "fc", "sc", "club"}
        abbrev = "".join(w[0].upper() for w in words if w.lower() not in skip)

        # Cap at 4 characters
        return abbrev[:4] if abbrev else team_name[:3].upper()

    def _team_in_match(
        self,
        team_id: str,
        teams_list: list[str],
        match_data: dict,
    ) -> bool:
        """Check if a team (by ID or name) is in a match.

        Team IDs are derived from names, so we check both the ID match
        and the raw team name in the teams array.
        """
        # Check by derived ID against team names in the match
        for team_name in teams_list:
            if self._team_ids_match(team_id, team_name):
                return True

        return False

    def _team_ids_match(self, team_id: str, team_name: str) -> bool:
        """Check if a team ID matches a team name.

        Since IDs are derived from names, we check both directions.
        """
        derived_id = self._make_team_id(team_name)
        if team_id == derived_id:
            return True

        # Also check if the team_name appears in the ID
        if team_name.lower() in team_id.lower():
            return True

        return False
