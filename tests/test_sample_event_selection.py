"""Tests for sample-event selection (template live preview).

The rule applies to ALL providers: prefer the most-recent FINAL game with two
teams (so postgame vars populate), else the nearest upcoming/in-progress game.
"""

from datetime import UTC, datetime, timedelta

from teamarr.core import Event, EventStatus, Team
from teamarr.services.sports_data import SportsDataService

NOW = datetime.now(UTC)


def _team(name: str) -> Team:
    return Team(
        id=name, provider="espn", name=name, short_name=name,
        abbreviation=name[:3].upper(), league="nba", sport="basketball",
    )


def _event(eid: str, start: datetime, state: str, *, away: bool = True) -> Event:
    return Event(
        id=eid, provider="espn", name=eid, short_name=eid, start_time=start,
        home_team=_team("Home_" + eid),
        away_team=_team("Away_" + eid) if away else None,  # type: ignore[arg-type]
        status=EventStatus(state=state), league="nba", sport="basketball",
    )


class _FakeProvider:
    """Provider exposing the bulk candidate path (like TSDB)."""

    def __init__(self, events):
        self._events = events

    def supports_league(self, league):
        return True

    def get_sample_candidates(self, league):
        return self._events


def _svc(events):
    return SportsDataService([_FakeProvider(events)])


def test_prefers_most_recent_final():
    old_final = _event("old", NOW - timedelta(days=5), "final")
    recent_final = _event("recent", NOW - timedelta(hours=3), "final")
    upcoming = _event("up", NOW + timedelta(days=1), "scheduled")
    ev = _svc([upcoming, old_final, recent_final]).get_sample_event("nba")
    assert ev is not None and ev.id == "recent"


def test_falls_back_to_nearest_upcoming_when_no_final():
    soon = _event("soon", NOW + timedelta(hours=2), "scheduled")
    far = _event("far", NOW + timedelta(days=10), "scheduled")
    ev = _svc([far, soon]).get_sample_event("nba")
    assert ev is not None and ev.id == "soon"


def test_ignores_events_missing_a_team():
    no_away = _event("noaway", NOW - timedelta(hours=1), "final", away=False)
    real = _event("real", NOW - timedelta(days=2), "final")
    ev = _svc([no_away, real]).get_sample_event("nba")
    assert ev is not None and ev.id == "real"


def test_none_when_no_candidates():
    assert _svc([]).get_sample_event("nba") is None
