"""Custom-league API endpoints (epic teamarrv2-eqz).

Hosts the custom-league feature: the premium-gated capability check (eqz.1),
and — landing in later beads — the TSDB-only CRUD write path (eqz.2) and the
live test-fetch validator (eqz.3). Read access to the full league catalogue
lives separately under ``/cache/leagues``.
"""

import logging

from fastapi import APIRouter

from teamarr.database import get_db
from teamarr.services.custom_leagues import (
    custom_leagues_enabled,
    supported_custom_league_sports,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/leagues")


@router.get("/custom/capability")
def get_custom_league_capability() -> dict:
    """Report whether the custom-league feature is unlocked, and its sport list.

    The feature is hard-gated behind a TheSportsDB premium key. The frontend
    uses ``enabled`` to lock/hide the UI and ``supported_sports`` to populate
    the sport dropdown (only matcher-backed sports — never free text).

    Returns:
        ``{enabled: bool, supported_sports: [{sport_code, display_name}]}``
    """
    with get_db() as conn:
        enabled = custom_leagues_enabled(conn)
        sports = supported_custom_league_sports(conn)

    return {"enabled": enabled, "supported_sports": sports}
