"""Tests for custom-league policy: premium gate (eqz.1) + sport guardrails (eqz.8).

These exercise the single source of truth in ``services/custom_leagues.py`` that
the write path (eqz.2) and the test-fetch validator (eqz.3) will both enforce.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from teamarr.services.custom_leagues import (
    ALLOWED_EVENT_TYPES,
    FUNCTIONAL_SPORTS,
    CustomLeagueGateError,
    CustomLeagueValidationError,
    custom_leagues_enabled,
    default_event_type,
    is_supported_sport,
    require_custom_leagues_enabled,
    supported_custom_league_sports,
    tsdb_sport_to_teamarr,
    validate_custom_league_sport,
    validate_event_type,
    validate_tsdb_sport_matches,
)

SCHEMA = Path(__file__).resolve().parents[1] / "teamarr" / "database" / "schema.sql"


def _db() -> sqlite3.Connection:
    """Fresh in-memory DB seeded from schema.sql (no premium key by default)."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA.read_text())
    return conn


def _set_key(conn: sqlite3.Connection, key: str | None) -> None:
    conn.execute("UPDATE settings SET tsdb_api_key = ? WHERE id = 1", (key,))


# ---------------------------------------------------------------------------
# Premium gate (eqz.1)
# ---------------------------------------------------------------------------


def test_gate_locked_without_key():
    conn = _db()
    assert custom_leagues_enabled(conn) is False
    with pytest.raises(CustomLeagueGateError):
        require_custom_leagues_enabled(conn)


def test_gate_unlocked_with_key():
    conn = _db()
    _set_key(conn, "premium-abc123")
    assert custom_leagues_enabled(conn) is True
    require_custom_leagues_enabled(conn)  # does not raise


@pytest.mark.parametrize("blank", ["", "   ", None])
def test_gate_treats_blank_key_as_locked(blank):
    conn = _db()
    _set_key(conn, blank)
    assert custom_leagues_enabled(conn) is False


# ---------------------------------------------------------------------------
# Sport allowlist (eqz.8)
# ---------------------------------------------------------------------------


def test_functional_sports_excludes_placeholder_sports():
    # Roadmap placeholders with no matcher must never be selectable.
    for placeholder in ("tennis", "golf", "racing", "wrestling"):
        assert placeholder not in FUNCTIONAL_SPORTS
        assert is_supported_sport(placeholder) is False


def test_functional_sports_includes_matcher_backed_sports():
    for sport in ("soccer", "cricket", "boxing", "mma", "hockey", "rugby"):
        assert is_supported_sport(sport) is True


def test_supported_sports_intersects_table_with_functional_set():
    conn = _db()
    sports = supported_custom_league_sports(conn)
    codes = {s["sport_code"] for s in sports}
    assert codes == set(FUNCTIONAL_SPORTS)
    # Placeholder sports are in the table but excluded from the picker.
    assert "tennis" not in codes
    # Display names come through for the UI.
    assert all(s["display_name"] for s in sports)


def test_validate_sport_rejects_unsupported():
    validate_custom_league_sport("soccer")  # ok
    with pytest.raises(CustomLeagueValidationError):
        validate_custom_league_sport("tennis")
    with pytest.raises(CustomLeagueValidationError):
        validate_custom_league_sport("underwater-hockey")


# ---------------------------------------------------------------------------
# event_type guardrail (eqz.8)
# ---------------------------------------------------------------------------


def test_default_event_type_by_sport():
    assert default_event_type("boxing") == "event_card"
    assert default_event_type("mma") == "event_card"
    assert default_event_type("soccer") == "team_vs_team"
    assert default_event_type("hockey") == "team_vs_team"


def test_validate_event_type():
    for et in ALLOWED_EVENT_TYPES:
        validate_event_type(et)
    with pytest.raises(CustomLeagueValidationError):
        validate_event_type("event")  # schema default but not matcher-supported
    with pytest.raises(CustomLeagueValidationError):
        validate_event_type("bogus")


# ---------------------------------------------------------------------------
# TSDB sport cross-check (eqz.8)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "str_sport,expected",
    [
        ("Soccer", "soccer"),
        ("soccer", "soccer"),
        ("  Cricket  ", "cricket"),
        ("Fighting", "mma"),
        ("Ice Hockey", "hockey"),
        ("American Football", "football"),
        ("Australian Football", "australian-football"),
        ("Curling", None),
        ("", None),
        (None, None),
    ],
)
def test_tsdb_sport_mapping(str_sport, expected):
    assert tsdb_sport_to_teamarr(str_sport) == expected


def test_cross_check_accepts_match():
    validate_tsdb_sport_matches("Soccer", "soccer")  # does not raise


def test_cross_check_rejects_mismatch():
    # User picked soccer but TSDB says it's cricket — the mislabel guardrail.
    with pytest.raises(CustomLeagueValidationError) as exc:
        validate_tsdb_sport_matches("Cricket", "soccer")
    assert "mismatch" in str(exc.value).lower()


def test_cross_check_rejects_unmapped_sport():
    with pytest.raises(CustomLeagueValidationError):
        validate_tsdb_sport_matches("Curling", "soccer")


# ---------------------------------------------------------------------------
# Capability endpoint (eqz.1) — structural smoke test against the live app
# ---------------------------------------------------------------------------


def test_capability_endpoint_shape():
    from fastapi.testclient import TestClient

    from teamarr.api.app import app

    resp = TestClient(app).get("/api/v1/leagues/custom/capability")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body["enabled"], bool)
    codes = {s["sport_code"] for s in body["supported_sports"]}
    assert codes == set(FUNCTIONAL_SPORTS)
    assert "tennis" not in codes  # placeholder sport never offered

