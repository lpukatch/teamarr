"""Tests for the summary/context variables (tvnk.10 free tier).

Covers the type-keyed headline selection in the ESPN provider and the three
raw-passthrough extractors: game_recap, game_event_note, soccer_match_note.
"""

from datetime import datetime

from teamarr.core.types import Event, EventStatus, Team
from teamarr.providers.espn.provider import ESPNProvider
from teamarr.templates.context import (
    GameContext,
    TeamChannelContext,
    TemplateContext,
)
from teamarr.templates.variables.soccer import extract_soccer_match_note
from teamarr.templates.variables.summary import (
    extract_game_event_note,
    extract_game_preview,
    extract_game_recap,
    extract_series_summary,
)


def _event(**kw) -> Event:
    base = dict(
        id="1",
        provider="espn",
        name="A vs B",
        short_name="A @ B",
        start_time=datetime(2026, 6, 17, 19, 0),
        league="nba",
        sport="basketball",
        status=EventStatus(state="post"),
        home_team=Team(
            id="1",
            provider="espn",
            name="B",
            short_name="B",
            abbreviation="B",
            league="nba",
            sport="basketball",
        ),
        away_team=Team(
            id="2",
            provider="espn",
            name="A",
            short_name="A",
            abbreviation="A",
            league="nba",
            sport="basketball",
        ),
    )
    base.update(kw)
    return Event(**base)


def _ctx(event: Event) -> tuple[TemplateContext, GameContext]:
    gc = GameContext(event=event)
    tc = TeamChannelContext(team_id="1", league="nba", sport="basketball", team_name="B")
    return TemplateContext(game_context=gc, team_config=tc, team_stats=None), gc


# --- type-keyed headline selection (the only real logic in the provider) ---


def test_headline_of_type_selects_by_tag():
    comp = {
        "headlines": [
            {"type": "Preview", "description": "preview text"},
            {"type": "Recap", "description": "recap text"},
        ]
    }
    assert ESPNProvider._headline_of_type(comp, "Recap") == "recap text"
    assert ESPNProvider._headline_of_type(comp, "Preview") == "preview text"


def test_headline_of_type_empty_when_absent():
    assert ESPNProvider._headline_of_type({}, "Recap") == ""
    assert ESPNProvider._headline_of_type({"headlines": []}, "Recap") == ""
    assert (
        ESPNProvider._headline_of_type(
            {"headlines": [{"type": "Preview", "description": "p"}]}, "Recap"
        )
        == ""
    )


# --- extractors are raw passthrough, empty when absent ---


def test_game_recap_passthrough():
    ctx, gc = _ctx(_event(game_recap="Brunson scored 45."))
    assert extract_game_recap(ctx, gc) == "Brunson scored 45."


def test_game_event_note_passthrough():
    ctx, gc = _ctx(_event(game_event_note="NBA Finals - Game 5"))
    assert extract_game_event_note(ctx, gc) == "NBA Finals - Game 5"


def test_soccer_match_note_passthrough():
    ctx, gc = _ctx(_event(soccer_match_note="FIFA World Cup, Group J"))
    assert extract_soccer_match_note(ctx, gc) == "FIFA World Cup, Group J"


def test_game_preview_passthrough():
    ctx, gc = _ctx(_event(game_preview="Toronto Blue Jays vs. Boston Red Sox"))
    assert extract_game_preview(ctx, gc) == "Toronto Blue Jays vs. Boston Red Sox"


def test_series_summary_passthrough():
    ctx, gc = _ctx(_event(series_summary="Series tied 1-1"))
    assert extract_series_summary(ctx, gc) == "Series tied 1-1"


def test_extractors_empty_when_unset():
    ctx, gc = _ctx(_event())
    for fn in (
        extract_game_recap,
        extract_game_event_note,
        extract_soccer_match_note,
        extract_game_preview,
        extract_series_summary,
    ):
        assert fn(ctx, gc) == ""


def test_extractors_safe_without_event():
    ctx, gc = _ctx(_event())
    ctx.game_context.event = None
    gc = ctx.game_context
    for fn in (
        extract_game_recap,
        extract_game_event_note,
        extract_soccer_match_note,
        extract_game_preview,
        extract_series_summary,
    ):
        assert fn(ctx, gc) == ""
