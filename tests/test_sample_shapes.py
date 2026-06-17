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
        assert data["home_team"] == "Sample City Sasquatches"
        assert data["team_name"] == "Sample City Sasquatches"
        assert data["opponent"] == "Mockingham Yetis"
        assert data["league"] == "Placeholder Premier League"
        assert data["league_abbrev"] == "PPL"
        assert data["venue"] == "The Placeholder Dome"


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
    assert data["fighter1"] == "Knuckles McTestface"
    assert data["fighter2"] == "Dummy Von Punchington"
    assert data["league"] == "Sample Fighting Championship"
    assert data["venue"] == "The Testing Octagon"


def test_racing_shape_uses_funny_drivers():
    data = get_all_sample_data_for_league("f1", "racing")
    assert data["race_winner"] == "Speedy McTestface"
    assert data["pole_position"] == "Speedy McTestface"
    assert data["circuit_name"] == "Mock Raceway"
    assert data["league"] == "Placeholder Grand Prix"
    assert data["league_abbrev"] == "PGP"
