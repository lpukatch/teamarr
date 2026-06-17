"""Tests for the 3-shape sample-data system (epic gruy .1/.2).

Every league previews against one of three generic, FICTITIOUS shapes
("team" / "combat" / "racing") so a sample never looks like a real (and likely
wrong-league) game. These tests pin the sport->shape mapping and assert the
funny placeholder identities surface for representative leagues of each shape.
"""

import pytest

from teamarr.templates.sample_data import (
    get_all_sample_data_for_league,
    resolve_shape,
)


@pytest.mark.parametrize(
    "sport,expected",
    [
        ("basketball", "team"),
        ("hockey", "team"),
        ("football", "team"),
        ("soccer", "team"),
        ("baseball", "team"),
        ("mma", "combat"),
        ("boxing", "combat"),
        ("racing", "racing"),
        ("", "team"),
        (None, "team"),
        ("UNKNOWN", "team"),
    ],
)
def test_resolve_shape(sport, expected):
    assert resolve_shape(sport) == expected


def test_team_shape_uses_funny_identities():
    """Team-sport leagues (incl. soccer) preview the fictitious team identity."""
    for code, sport in [
        ("nba", "basketball"),
        ("nhl", "hockey"),
        ("usa.nwsl", "soccer"),
    ]:
        data = get_all_sample_data_for_league(code, sport)
        assert data["home_team"] == "Flint Tropics"
        assert data["team_name"] == "Flint Tropics"
        assert data["opponent"] == "Greenwich Mean Time"
        assert data["league"] == "Placeholder Premier League"
        assert data["league_abbrev"] == "PPL"
        assert data["venue"] == "The Coconut Coliseum"


def test_team_shape_carries_both_pro_and_college_fields():
    """One shape must fill BOTH pro (conference) AND college (rank) identity so
    pro and college templates both render — no real league has both."""
    data = get_all_sample_data_for_league("nba", "basketball")
    assert data["pro_conference"]  # non-empty pro-style field
    assert data["pro_division"]
    assert data["team_rank"]  # non-empty college/AP-style field
    assert data["college_conference"]


def test_combat_shape_uses_funny_fighters():
    data = get_all_sample_data_for_league("ufc", "mma")
    assert data["fighter1"] == "Little Mac"
    assert data["fighter2"] == "Super Macho Man"
    assert data["league"] == "World Video Boxing Association"
    assert data["venue"] == "Madison Square Pixels"


def test_racing_shape_uses_funny_drivers():
    data = get_all_sample_data_for_league("f1", "racing")
    assert data["race_winner"] == "Ricky Bobby"
    assert data["pole_position"] == "Lightning McQueen"
    assert data["circuit_name"] == "Radiator Springs Speedway"
    assert data["league"] == "Piston Cup Series"
    assert data["league_abbrev"] == "PCS"


def test_team_shape_has_no_real_team_leak():
    """Regression guard: no real franchise/RSN may bleed into the fictitious
    team shape. A substring-replace bug once leaked 'Detroit Pistons' into the
    .next/.last matchups when the override keys got corrupted."""
    blob = " ".join(str(v) for v in get_all_sample_data_for_league("nba", "basketball").values())
    for token in ("Pistons", "Bucks", "Cavaliers", "Lakers", "Bulls",
                  "Detroit", "Milwaukee", "Cleveland", "Bally Sports"):
        assert token not in blob, f"real-team leak in team sample: {token!r}"
