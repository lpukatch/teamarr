"""Integration tests for the EPG path in StreamMatcher (teamarrv2-183.4).

StreamMatcher's constructor does DB work, so we exercise the EPG-specific
orchestration methods (_match_via_epg, _reconcile_epg) on a bare instance with
the few attributes they touch, patching the shared routing. This isolates the
EPG logic: category gating, EPG/window tagging, fan-out, and reconciliation.
"""

from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace

from teamarr.consumers.matching.epg_index import EPGProgramIndex
from teamarr.consumers.matching.matcher import MatchedStreamResult, StreamMatcher
from teamarr.consumers.matching.result import MatchMethod, MatchOutcome
from teamarr.dispatcharr.types import DispatcharrProgram

BASE = datetime(2026, 6, 1, 18, tzinfo=UTC)


def _prog(title="MLB Baseball", sub="Chicago Cubs at St. Louis Cardinals", cats=(), start=BASE):
    return DispatcharrProgram.from_api(
        {
            "id": 1,
            "tvg_id": "espn",
            "title": title,
            "sub_title": sub,
            "start_time": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "end_time": (start + timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "epg_source": "ext",
            "custom_properties": {"categories": list(cats)} if cats else {},
        }
    )


def _bare_matcher(index, team_streams_enabled=True):
    """A StreamMatcher with only the fields the EPG methods touch."""
    m = object.__new__(StreamMatcher)
    m._epg_index = index
    m._custom_regex = None
    m._feed_home_terms = None
    m._feed_away_terms = None
    m._team_streams_enabled = team_streams_enabled
    m._league_event_types = {}
    return m


def _matched_outcome():
    event = SimpleNamespace(league="mlb")
    return MatchOutcome.matched(MatchMethod.FUZZY, event=event, confidence=0.9)


# ============================================================= _match_via_epg


def test_match_via_epg_tags_method_and_window(monkeypatch):
    index = EPGProgramIndex({"espn": [_prog()]})
    m = _bare_matcher(index)
    monkeypatch.setattr(m, "_route_to_outcomes", lambda c, sid, td: [_matched_outcome()])
    # passthrough: return the (now-tagged) outcome so we can assert on it
    monkeypatch.setattr(m, "_outcome_to_result", lambda outcome, **kw: outcome)

    out = m._match_via_epg(100, "ESPN", "espn", date(2026, 6, 1))
    assert len(out) == 1
    assert out[0].match_method == MatchMethod.EPG
    assert out[0].epg_program_start == BASE
    assert out[0].epg_program_end == BASE + timedelta(hours=3)


def test_match_via_epg_skips_non_event_before_routing(monkeypatch):
    index = EPGProgramIndex({"espn": [_prog(cats=("Sports non-event",))]})
    m = _bare_matcher(index)
    routed = []
    monkeypatch.setattr(m, "_route_to_outcomes", lambda *a: routed.append(1) or [])
    out = m._match_via_epg(100, "ESPN", "espn", date(2026, 6, 1))
    assert out == []
    assert not routed  # gated by should_attempt() before the matcher runs


def test_match_via_epg_skips_classic_replay(monkeypatch):
    index = EPGProgramIndex({"espn": [_prog(cats=("Sports event", "Classic Sport Event"))]})
    m = _bare_matcher(index)
    routed = []
    monkeypatch.setattr(m, "_route_to_outcomes", lambda *a: routed.append(1) or [])
    assert m._match_via_epg(100, "ESPN", "espn", date(2026, 6, 1)) == []
    assert not routed


def test_match_via_epg_fans_out_one_per_program(monkeypatch):
    progs = [
        _prog(sub="Chicago Cubs at St. Louis Cardinals", start=BASE),
        _prog(sub="Los Angeles Lakers at Boston Celtics", start=BASE + timedelta(hours=4)),
    ]
    index = EPGProgramIndex({"espn": progs})
    m = _bare_matcher(index)
    monkeypatch.setattr(m, "_route_to_outcomes", lambda c, sid, td: [_matched_outcome()])
    monkeypatch.setattr(m, "_outcome_to_result", lambda outcome, **kw: outcome)
    out = m._match_via_epg(100, "ESPN", "espn", date(2026, 6, 1))
    # one matched result per program, each with its own window
    assert len(out) == 2
    assert out[0].epg_program_start == BASE
    assert out[1].epg_program_start == BASE + timedelta(hours=4)


def test_match_via_epg_drops_unmatched_outcomes(monkeypatch):
    index = EPGProgramIndex({"espn": [_prog()]})
    m = _bare_matcher(index)
    monkeypatch.setattr(
        m, "_route_to_outcomes",
        lambda c, sid, td: [MatchOutcome.failed(None)],  # not matched
    )
    assert m._match_via_epg(100, "ESPN", "espn", date(2026, 6, 1)) == []


# ============================================================== _reconcile_epg


def _result(matched, method=MatchMethod.FUZZY):
    return MatchedStreamResult(
        stream_name="x", stream_id=1, matched=matched, match_method=method
    )


def _epg_result():
    return MatchedStreamResult(
        stream_name="x", stream_id=1, matched=True, match_method=MatchMethod.EPG,
        epg_program_start=BASE,
    )


def test_reconcile_linear_epg_wins_over_name():
    # two programs => linear; EPG matched => EPG wins, name discarded
    index = EPGProgramIndex({"espn": [_prog(), _prog(start=BASE + timedelta(hours=4))]})
    m = _bare_matcher(index)
    name = [_result(matched=True)]
    epg = [_epg_result(), _epg_result()]
    out = m._reconcile_epg(name, epg, "espn")
    assert out == epg


def test_reconcile_linear_no_epg_keeps_name():
    index = EPGProgramIndex({"espn": [_prog(), _prog(start=BASE + timedelta(hours=4))]})
    m = _bare_matcher(index)
    name = [_result(matched=False)]
    out = m._reconcile_epg(name, [], "espn")
    assert out == name


def test_reconcile_dedicated_name_wins():
    # single program => dedicated; name match kept even if EPG also matched
    index = EPGProgramIndex({"espn": [_prog()]})
    m = _bare_matcher(index)
    name = [_result(matched=True)]
    epg = [_epg_result()]
    out = m._reconcile_epg(name, epg, "espn")
    assert out == name


def test_reconcile_dedicated_epg_fills_when_name_empty():
    index = EPGProgramIndex({"espn": [_prog()]})
    m = _bare_matcher(index)
    name = [_result(matched=False)]
    epg = [_epg_result()]
    out = m._reconcile_epg(name, epg, "espn")
    assert out == epg
