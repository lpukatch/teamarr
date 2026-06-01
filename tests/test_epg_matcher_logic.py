"""Tests for EPG program-data matching logic (teamarrv2-183.4 pure helpers).

Grounded in the live-probe findings: teams in sub_title, category gating with
classic-replay precedence, and graceful fallback when categories are absent.
"""

from teamarr.consumers.matching.epg_matcher import (
    EPGMatchPolicy,
    build_match_input,
    classify_program_policy,
    should_attempt,
)
from teamarr.dispatcharr.types import DispatcharrProgram


def _prog(title="MLB Baseball", sub_title="Chicago Cubs at St. Louis Cardinals", cats=()):
    return DispatcharrProgram.from_api(
        {
            "id": 1,
            "tvg_id": "espn",
            "title": title,
            "sub_title": sub_title,
            "custom_properties": {"categories": list(cats)} if cats else {},
        }
    )


# =============================================================== category gate


def test_sports_event_attempts():
    assert classify_program_policy(("Sports", "Sports event", "Baseball")) is EPGMatchPolicy.ATTEMPT


def test_sports_non_event_skips():
    p = ("Show", "Sports non-event", "Sports talk")
    assert classify_program_policy(p) is EPGMatchPolicy.SKIP_NON_EVENT


def test_classic_skips():
    assert classify_program_policy(("Sports", "Classic Sport Event")) is EPGMatchPolicy.SKIP_CLASSIC


def test_classic_takes_precedence_over_event():
    # Replays carry BOTH tags — classic must win (Super Bowl Classics, UFC Reloaded)
    cats = ("Sports", "Sports event", "Classic Sport Event", "Football")
    assert classify_program_policy(cats) is EPGMatchPolicy.SKIP_CLASSIC


def test_empty_categories_attempt_fallback():
    assert classify_program_policy(()) is EPGMatchPolicy.ATTEMPT


def test_unknown_categories_attempt():
    # Has categories, but none decisive → attempt, rely on team-match + window
    assert classify_program_policy(("Sports", "Baseball")) is EPGMatchPolicy.ATTEMPT


def test_category_matching_is_case_insensitive():
    assert classify_program_policy(("SPORTS NON-EVENT",)) is EPGMatchPolicy.SKIP_NON_EVENT


# =============================================================== input builder


def test_build_input_combines_title_and_subtitle():
    p = _prog("MLB Baseball", "Chicago Cubs at St. Louis Cardinals")
    assert build_match_input(p) == "MLB Baseball Chicago Cubs at St. Louis Cardinals"


def test_build_input_generic_title_no_subtitle():
    p = _prog("NHL Hockey", None)
    assert build_match_input(p) == "NHL Hockey"


def test_build_input_strips_and_skips_empty():
    p = _prog("  Soccer  ", "")
    assert build_match_input(p) == "Soccer"


def test_build_input_empty_when_both_blank():
    p = _prog("", None)
    assert build_match_input(p) == ""


# =================================================================== combined


def test_should_attempt_true_for_real_game():
    assert should_attempt(_prog(cats=("Sports event",))) is True


def test_should_attempt_false_for_non_event():
    assert should_attempt(_prog(cats=("Sports non-event",))) is False


def test_should_attempt_false_for_classic():
    assert should_attempt(_prog(cats=("Sports event", "Classic Sport Event"))) is False


def test_should_attempt_true_for_generic_title_input():
    # "NHL Hockey" is a non-empty input → we attempt; TeamMatcher self-rejects
    # downstream (no teams). We don't duplicate team extraction here.
    assert should_attempt(_prog("NHL Hockey", None)) is True


def test_should_attempt_false_when_match_input_empty():
    # truly nothing to match on
    assert should_attempt(_prog("", None)) is False
