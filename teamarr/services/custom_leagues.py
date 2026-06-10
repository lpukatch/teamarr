"""Custom-league policy: premium gate and sport guardrails.

Single source of truth for the rules that govern user-added (custom) leagues
(epic ``teamarrv2-eqz``). Custom leagues are TSDB-only and the whole feature is
gated behind a TheSportsDB *premium* key. These helpers are consumed by the
custom-league write routes (``eqz.2``) and the live test-fetch / validation
endpoint (``eqz.3``); keeping them here means the UI, the write path, and the
validator all enforce the same policy.

Why a hard premium gate (``eqz.1``):
    TSDB's free tier is too thin for arbitrary leagues — ``eventsnextleague``
    returns ~5 events/day and ``lookupteam`` is broken — so a free-tier custom
    league would silently produce empty guides. Gating on a premium key keeps
    that failure mode out of the product.

Why sport guardrails (``eqz.8``):
    A league's ``sport`` selects which matcher and ``event_type`` logic runs. A
    free-text or unsupported sport routes the league through the wrong pipeline
    and silently emits broken channels. We therefore restrict custom leagues to
    the sports that actually have a working matcher, and cross-check the chosen
    sport against what TSDB reports for the league.
"""

from __future__ import annotations

import sqlite3

from teamarr.database.settings.read import get_tsdb_api_key

# ---------------------------------------------------------------------------
# Sport guardrails (eqz.8)
# ---------------------------------------------------------------------------

# Sports that have a working matcher today. This is intentionally NARROWER than
# the ``sports`` table (17 rows): tennis, golf, racing, and wrestling are seeded
# as placeholders for roadmap epics (mf7 tennis, 1tz golf, h31 motorsports) but
# have no matcher, so a custom league under them would generate broken output.
# When one of those sports ships a real matcher, add its code here.
FUNCTIONAL_SPORTS: frozenset[str] = frozenset(
    {
        "australian-football",
        "baseball",
        "basketball",
        "boxing",
        "cricket",
        "football",
        "hockey",
        "lacrosse",
        "mma",
        "rugby",
        "soccer",
        "softball",
        "volleyball",
    }
)

# The only ``event_type`` values the matching pipeline understands.
ALLOWED_EVENT_TYPES: frozenset[str] = frozenset({"team_vs_team", "event_card"})

# Sports whose events are cards of individual bouts rather than two-team games;
# these default to ``event_card``. Everything else defaults to ``team_vs_team``.
_EVENT_CARD_SPORTS: frozenset[str] = frozenset({"boxing", "mma"})

# Maps TSDB ``strSport`` values to Teamarr sport codes. Used to cross-check the
# user's chosen sport against what TSDB actually reports for the league. Any
# value not present here resolves to ``None`` and fails the cross-check, which
# is the safe default (reject rather than mislabel).
_TSDB_SPORT_TO_TEAMARR: dict[str, str] = {
    "soccer": "soccer",
    "cricket": "cricket",
    "rugby": "rugby",
    "boxing": "boxing",
    "fighting": "mma",
    "ice hockey": "hockey",
    "baseball": "baseball",
    "basketball": "basketball",
    "american football": "football",
    "australian football": "australian-football",
    "volleyball": "volleyball",
    "lacrosse": "lacrosse",
    "softball": "softball",
}


class CustomLeagueValidationError(ValueError):
    """A custom-league field failed a guardrail (maps to HTTP 400)."""


class CustomLeagueGateError(PermissionError):
    """The custom-league feature is locked (no premium key; maps to HTTP 403)."""


# ---------------------------------------------------------------------------
# Premium gate (eqz.1)
# ---------------------------------------------------------------------------


def custom_leagues_enabled(conn: sqlite3.Connection) -> bool:
    """Return whether the custom-league feature is unlocked for this install.

    The single gate signal is the presence of a TheSportsDB premium key in
    settings — the same key that flips the TSDB client into premium mode
    (``providers/__init__.py``).
    """
    key = get_tsdb_api_key(conn)
    return bool(key and key.strip())


def require_custom_leagues_enabled(conn: sqlite3.Connection) -> None:
    """Raise :class:`CustomLeagueGateError` if the feature is locked."""
    if not custom_leagues_enabled(conn):
        raise CustomLeagueGateError(
            "Custom leagues require a TheSportsDB premium key. "
            "Add one in Settings > System > TheSportsDB API Key."
        )


# ---------------------------------------------------------------------------
# Sport / event-type helpers
# ---------------------------------------------------------------------------


def is_supported_sport(sport: str) -> bool:
    """Return whether ``sport`` is a matcher-backed (functional) sport."""
    return sport in FUNCTIONAL_SPORTS


def supported_custom_league_sports(conn: sqlite3.Connection) -> list[dict]:
    """List functional sports as ``{sport_code, display_name}`` for the UI.

    Intersects the ``sports`` table (for display names) with
    :data:`FUNCTIONAL_SPORTS`, sorted by display name. This is what the
    custom-league form's sport dropdown should offer — never free text.
    """
    rows = conn.execute(
        "SELECT sport_code, display_name FROM sports ORDER BY display_name"
    ).fetchall()
    return [
        {"sport_code": r["sport_code"], "display_name": r["display_name"]}
        for r in rows
        if r["sport_code"] in FUNCTIONAL_SPORTS
    ]


def default_event_type(sport: str) -> str:
    """Return the sensible default ``event_type`` for a sport."""
    return "event_card" if sport in _EVENT_CARD_SPORTS else "team_vs_team"


def tsdb_sport_to_teamarr(tsdb_str_sport: str | None) -> str | None:
    """Map a TSDB ``strSport`` to a Teamarr sport code (None if unmapped)."""
    if not tsdb_str_sport:
        return None
    return _TSDB_SPORT_TO_TEAMARR.get(tsdb_str_sport.strip().lower())


def validate_custom_league_sport(sport: str) -> None:
    """Raise :class:`CustomLeagueValidationError` if ``sport`` isn't functional."""
    if sport not in FUNCTIONAL_SPORTS:
        raise CustomLeagueValidationError(
            f"Sport '{sport}' is not supported for custom leagues. "
            f"Choose one of: {', '.join(sorted(FUNCTIONAL_SPORTS))}."
        )


def validate_event_type(event_type: str) -> None:
    """Raise :class:`CustomLeagueValidationError` for an unknown ``event_type``."""
    if event_type not in ALLOWED_EVENT_TYPES:
        raise CustomLeagueValidationError(
            f"event_type '{event_type}' is invalid. "
            f"Must be one of: {', '.join(sorted(ALLOWED_EVENT_TYPES))}."
        )


def validate_tsdb_sport_matches(tsdb_str_sport: str | None, chosen_sport: str) -> None:
    """Cross-check TSDB's sport for a league against the user's chosen sport.

    Prevents mislabeling (e.g. picking ``soccer`` for a league TSDB classifies
    as cricket), which would route the league through the wrong matcher. An
    unmapped TSDB sport is treated as a mismatch — reject rather than guess.
    """
    mapped = tsdb_sport_to_teamarr(tsdb_str_sport)
    if mapped is None:
        raise CustomLeagueValidationError(
            f"TheSportsDB reports sport '{tsdb_str_sport}', which Teamarr does "
            "not support for custom leagues."
        )
    if mapped != chosen_sport:
        raise CustomLeagueValidationError(
            f"Sport mismatch: you selected '{chosen_sport}' but TheSportsDB "
            f"classifies this league as '{mapped}' (strSport '{tsdb_str_sport}')."
        )
