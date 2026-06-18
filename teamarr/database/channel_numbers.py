"""Channel numbering and range management.

Two global modes:
- AUTO: Sequential numbering from channel_range_start, ordered by sort priorities
- MANUAL: Per-league starting channel numbers from league_channel_starts

Sort order is always: sport_priority → league_priority → event_time → event_id
Priorities come from channel_sort_priorities table (drag-drop UI).
"""

import json
import logging
import sqlite3
from datetime import datetime
from sqlite3 import Connection

logger = logging.getLogger(__name__)

MAX_CHANNEL = 999999  # Effectively no limit per Dispatcharr update

# Assign a channel its number and mark it sticky (gap/strict modes).
_SET_NUMBER_LOCKED_SQL = (
    "UPDATE managed_channels SET channel_number = ?, channel_number_locked = 1 WHERE id = ?"
)
# Lock a channel in place without changing its number.
_LOCK_SQL = "UPDATE managed_channels SET channel_number_locked = 1 WHERE id = ?"


# =============================================================================
# Settings Accessors
# =============================================================================


def get_global_channel_range(conn: Connection) -> tuple[int, int | None]:
    """Get global channel range settings.

    Returns:
        Tuple of (range_start, range_end). range_end may be None (no limit).
    """
    cursor = conn.execute(
        "SELECT channel_range_start, channel_range_end FROM settings WHERE id = 1"
    )
    row = cursor.fetchone()
    if not row:
        return 101, None
    return row["channel_range_start"] or 101, row["channel_range_end"]


def get_global_channel_mode(conn: Connection) -> str:
    """Get the global channel numbering mode.

    Returns:
        'auto' or 'manual'
    """
    cursor = conn.execute("SELECT global_channel_mode FROM settings WHERE id = 1")
    row = cursor.fetchone()
    if not row or not row["global_channel_mode"]:
        return "auto"
    mode = row["global_channel_mode"]
    return mode if mode in ("auto", "manual") else "auto"


def get_league_channel_starts(conn: Connection) -> dict[str, int]:
    """Get per-league starting channel numbers for MANUAL mode.

    Returns:
        Dict mapping league_code → starting channel number.
    """
    cursor = conn.execute("SELECT league_channel_starts FROM settings WHERE id = 1")
    row = cursor.fetchone()
    if not row or not row["league_channel_starts"]:
        return {}
    try:
        starts = json.loads(row["league_channel_starts"])
        return {k: int(v) for k, v in starts.items()} if isinstance(starts, dict) else {}
    except (json.JSONDecodeError, TypeError, ValueError):
        return {}


def get_global_consolidation_mode(conn: Connection) -> str:
    """Get the global stream consolidation mode.

    Returns:
        'consolidate' or 'separate'
    """
    try:
        cursor = conn.execute(
            "SELECT global_consolidation_mode FROM settings WHERE id = 1"
        )
        row = cursor.fetchone()
    except sqlite3.OperationalError:
        return "consolidate"
    if not row or not row["global_consolidation_mode"]:
        return "consolidate"
    mode = row["global_consolidation_mode"]
    return mode if mode in ("consolidate", "separate") else "consolidate"


def get_channel_stability_settings(conn: Connection) -> dict:
    """Get channel numbering stability settings.

    Stability mode governs how *existing* channel numbers behave across runs
    (AUTO mode only — MANUAL keeps its per-league sequential behavior):

    - 'compact': re-sort everyone into contiguous priority order every run (legacy).
    - 'gap':     sticky; new channels slot into a free number in their sorted
                 neighbourhood (gap_size spacing) or append; existing channels
                 never move except at the daily reset.
    - 'strict':  sticky; new channels append to the end of the used range so they
                 never displace anyone; gaps reclaimed only at the daily reset.

    Returns:
        Dict with keys: mode, gap_size, reset_enabled, reset_time, last_reset_at
    """
    defaults = {
        "mode": "compact",
        "gap_size": 1,
        "reset_enabled": True,
        "reset_time": "04:00",
        "last_reset_at": None,
    }
    try:
        cursor = conn.execute(
            """SELECT channel_stability_mode, channel_gap_size,
                      channel_daily_reset_enabled, channel_daily_reset_time,
                      last_channel_reset_at
               FROM settings WHERE id = 1"""
        )
        row = cursor.fetchone()
    except sqlite3.OperationalError:
        return defaults

    if not row:
        return defaults

    mode = row["channel_stability_mode"] or "compact"
    if mode not in ("compact", "gap", "strict"):
        mode = "compact"

    try:
        gap = int(row["channel_gap_size"]) if row["channel_gap_size"] else 1
    except (ValueError, TypeError):
        gap = 1
    gap = max(1, gap)

    reset_enabled = row["channel_daily_reset_enabled"]
    reset_enabled = True if reset_enabled is None else bool(reset_enabled)

    return {
        "mode": mode,
        "gap_size": gap,
        "reset_enabled": reset_enabled,
        "reset_time": row["channel_daily_reset_time"] or "04:00",
        "last_reset_at": row["last_channel_reset_at"],
    }


def is_sticky_mode(conn: Connection) -> bool:
    """True when channels should be sticky (AUTO + gap/strict stability mode).

    Used to skip the mid-run reassign passes: in sticky modes the only place
    numbers are (re)assigned is the single end-of-run pass, which also pushes to
    Dispatcharr, so intermediate passes would write DB numbers that never sync.
    """
    if get_global_channel_mode(conn) == "manual":
        return False
    return get_channel_stability_settings(conn)["mode"] in ("gap", "strict")


def should_run_channel_reset(conn: Connection) -> bool:
    """Whether the daily full re-layout should run on this generation.

    True only for gap/strict modes when the reset is enabled and this is the
    first generation at/after the configured local reset time today. This is
    how the reset "fits into generation windows" — no separate scheduler.
    """
    if get_global_channel_mode(conn) == "manual":
        return False
    settings = get_channel_stability_settings(conn)
    if settings["mode"] == "compact" or not settings["reset_enabled"]:
        return False

    from datetime import time as _time

    try:
        hh, mm = str(settings["reset_time"]).split(":")
        boundary_time = _time(int(hh), int(mm))
    except (ValueError, AttributeError):
        boundary_time = _time(4, 0)

    now = datetime.now()
    boundary = datetime.combine(now.date(), boundary_time)
    if now < boundary:
        return False

    last = settings["last_reset_at"]
    if not last:
        return True
    try:
        last_dt = datetime.fromisoformat(last)
    except (ValueError, TypeError):
        return True
    return last_dt < boundary


def _mark_channel_reset(conn: Connection) -> None:
    """Record that the daily full re-layout has run (resets the daily gate)."""
    conn.execute(
        "UPDATE settings SET last_channel_reset_at = ? WHERE id = 1",
        (datetime.now().isoformat(),),
    )


def _table_has_column(conn: Connection, table: str, column: str) -> bool:
    """Return True if `table` has `column` (defensive for un-reconciled DBs/tests)."""
    try:
        cols = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
    except sqlite3.OperationalError:
        return False
    return column in cols


# =============================================================================
# Channel Number Allocation
# =============================================================================


def _get_all_used_channels(conn: Connection) -> set[int]:
    """Get all channel numbers used by enabled groups.

    Returns:
        Set of all used channel numbers across all groups.
    """
    cursor = conn.execute(
        """SELECT mc.channel_number
           FROM managed_channels mc
           LEFT JOIN event_epg_groups g ON mc.event_epg_group_id = g.id
           WHERE (g.enabled = 1 OR mc.event_epg_group_id IS NULL)
             AND mc.deleted_at IS NULL"""
    )

    used_set = set()
    for row in cursor.fetchall():
        if row["channel_number"]:
            try:
                used_set.add(int(float(row["channel_number"])))
            except (ValueError, TypeError):
                pass
    return used_set


def get_next_channel_number(
    conn: Connection,
    league: str | None = None,
    external_occupied: set[int] | None = None,
) -> int | None:
    """Get the next available channel number.

    Unified entry point for channel allocation. Delegates to AUTO or MANUAL
    mode based on global_channel_mode setting.

    Args:
        conn: Database connection
        league: League code for the event (used in MANUAL mode for per-league starts)
        external_occupied: Channel numbers occupied by non-Teamarr channels (#146)

    Returns:
        Next available channel number, or None if range exhausted
    """
    mode = get_global_channel_mode(conn)
    if mode == "manual":
        return _get_next_manual_channel(conn, league, external_occupied)
    return _get_next_auto_channel(conn, external_occupied)


def _get_next_auto_channel(
    conn: Connection,
    external_occupied: set[int] | None = None,
) -> int | None:
    """Get next available channel in AUTO mode.

    Finds the first unused channel number starting from range_start,
    considering all channels across all enabled groups and external
    Dispatcharr channels.

    Args:
        conn: Database connection
        external_occupied: Channel numbers occupied by non-Teamarr channels (#146)

    Returns:
        Next available channel number, or None if range exhausted
    """
    range_start, range_end = get_global_channel_range(conn)
    effective_end = range_end if range_end else MAX_CHANNEL

    used_set = _get_all_used_channels(conn)
    if external_occupied:
        used_set |= external_occupied

    next_num = range_start
    while next_num in used_set:
        next_num += 1
        if next_num > effective_end:
            logger.warning(
                "[CHANNEL_NUM] AUTO: No available channels (range %d-%d exhausted)",
                range_start, effective_end,
            )
            return None

    if next_num > MAX_CHANNEL:
        logger.warning("[CHANNEL_NUM] Channel number %d exceeds max %d", next_num, MAX_CHANNEL)
        return None

    return next_num


def _get_next_manual_channel(
    conn: Connection,
    league: str | None = None,
    external_occupied: set[int] | None = None,
) -> int | None:
    """Get next available channel in MANUAL mode.

    Uses per-league starting channel numbers. Leagues without configured
    starts fall back to global range (auto-assign from range_start).

    Args:
        conn: Database connection
        league: League code for the event
        external_occupied: Channel numbers occupied by non-Teamarr channels (#146)

    Returns:
        Next available channel number, or None if range exhausted
    """
    league_starts = get_league_channel_starts(conn)
    range_start, range_end = get_global_channel_range(conn)
    effective_end = range_end if range_end else MAX_CHANNEL

    # Determine starting number for this league
    start = league_starts.get(league) if league else None
    if start is None:
        # Fallback: auto-assign from global range
        start = range_start

    used_set = _get_all_used_channels(conn)
    if external_occupied:
        used_set |= external_occupied

    next_num = start
    while next_num in used_set:
        next_num += 1
        if next_num > effective_end:
            logger.warning(
                "[CHANNEL_NUM] MANUAL: No channels for league '%s' (from %d, end %d)",
                league, start, effective_end,
            )
            return None

    if next_num > MAX_CHANNEL:
        logger.warning("[CHANNEL_NUM] Channel number %d exceeds max %d", next_num, MAX_CHANNEL)
        return None

    return next_num


# =============================================================================
# Global Sorting & Reassignment
# =============================================================================


def get_all_channels_sorted(conn: Connection) -> list[dict]:
    """Get all active channels sorted by sport/league/time/event_id.

    Fetches all active channels from enabled groups and sorts them according
    to the sort_priorities table and event start times.

    Sort order:
    0. Priority team (followed teams float to the very top — channel_priority_teams)
    1. Sport priority (from channel_sort_priorities, lower = earlier)
    2. League priority (from channel_sort_priorities, lower = earlier)
    3. Event start time (earlier = earlier)
    4. Event ID (deterministic for same time)
    5. Main channel before keyword channels

    Returns:
        List of channel dicts with sort-relevant fields, ordered globally
    """
    from teamarr.database.priority_teams import get_priority_team_match_keys
    from teamarr.database.sort_priorities import get_all_sort_priorities

    # 1. Get sort priorities (normalize to lowercase for case-insensitive matching)
    priorities = get_all_sort_priorities(conn)
    sport_order = {p.sport.lower(): p.sort_priority for p in priorities if p.league_code is None}
    league_order = {
        (p.sport.lower(), p.league_code.lower() if p.league_code else None): p.sort_priority
        for p in priorities
        if p.league_code is not None
    }

    # Priority teams: (sport_lower, team_name_lower) keys; a channel floats to the
    # top if either its home or away team matches one (see channel_priority_teams).
    priority_keys = get_priority_team_match_keys(conn)

    # 2. Get all channels from enabled groups with event info.
    # channel_number_locked may be absent on un-reconciled DBs / partial test
    # schemas — fall back to 0 (treated as not-yet-placed) when missing.
    locked_col = (
        "mc.channel_number_locked"
        if _table_has_column(conn, "managed_channels", "channel_number_locked")
        else "0 AS channel_number_locked"
    )
    cursor = conn.execute(f"""
        SELECT
            mc.id,
            mc.dispatcharr_channel_id,
            mc.channel_number,
            {locked_col},
            mc.channel_name,
            mc.event_epg_group_id,
            mc.primary_stream_id,
            mc.event_id,
            mc.sport,
            mc.league,
            mc.home_team,
            mc.away_team,
            mc.event_date,
            mc.exception_keyword,
            mc.created_at
        FROM managed_channels mc
        LEFT JOIN event_epg_groups g ON mc.event_epg_group_id = g.id
        WHERE (g.enabled = 1 OR mc.event_epg_group_id IS NULL)
          AND mc.deleted_at IS NULL
    """)

    channels = []
    for row in cursor.fetchall():
        channels.append(
            {
                "id": row["id"],
                "dispatcharr_channel_id": row["dispatcharr_channel_id"],
                "channel_number": row["channel_number"],
                "channel_number_locked": row["channel_number_locked"],
                "channel_name": row["channel_name"],
                "event_epg_group_id": row["event_epg_group_id"],
                "primary_stream_id": row["primary_stream_id"],
                "event_id": row["event_id"],
                "sport": row["sport"],
                "league": row["league"],
                "home_team": row["home_team"],
                "away_team": row["away_team"],
                "event_date": row["event_date"],
                "exception_keyword": row["exception_keyword"],
                "created_at": row["created_at"],
            }
        )

    # 3. Sort by: priority team → sport priority → league priority → time → event_id → keyword
    def sort_key(ch):
        sport = ch.get("sport") or ""
        league = ch.get("league") or ""
        event_date_str = ch.get("event_date")
        event_id = ch.get("event_id") or ""
        keyword = ch.get("exception_keyword") or ""

        sport_lower = sport.lower()
        league_lower = league.lower()

        # Priority-team tier (0 = priority, 1 = normal): match either team by name
        # within sport. Sorts first so followed teams lead, then normal ordering.
        home = (ch.get("home_team") or "").lower()
        away = (ch.get("away_team") or "").lower()
        is_priority = (sport_lower, home) in priority_keys or (sport_lower, away) in priority_keys
        priority_tier = 0 if is_priority else 1

        sport_pri = sport_order.get(sport_lower, 9999)
        league_pri = league_order.get((sport_lower, league_lower), 9999)

        # Parse event date
        if event_date_str:
            try:
                if "T" in str(event_date_str):
                    event_date = datetime.fromisoformat(str(event_date_str).replace("Z", "+00:00"))
                else:
                    event_date = datetime.strptime(str(event_date_str), "%Y-%m-%d %H:%M:%S")
                event_date = event_date.replace(tzinfo=None)
            except (ValueError, TypeError):
                event_date = datetime.max
        else:
            event_date = datetime.max

        # Main channel (no keyword) sorts before keyword channels
        keyword_sort = (0, "") if not keyword else (1, keyword)

        return (priority_tier, sport_pri, league_pri, event_date, str(event_id), keyword_sort)

    sorted_channels = sorted(channels, key=sort_key)

    logger.debug(
        "[CHANNEL_SORT] Global sort: %d channels, %d sport priorities, "
        "%d league priorities, %d priority teams",
        len(sorted_channels), len(sport_order), len(league_order), len(priority_keys),
    )

    return sorted_channels


def reassign_all_channels(
    conn: Connection,
    external_occupied: set[int] | None = None,
    force_reset: bool = False,
) -> dict:
    """Reassign all active channel numbers based on global mode.

    AUTO: behaviour depends on the channel stability mode:
        - compact: sequential numbers from range_start by sort priority (legacy).
        - gap/strict: sticky — existing (locked) channels keep their number; only
          unplaced channels are assigned. A full re-layout runs only when
          force_reset=True (the daily reset window).
    MANUAL: Sequential within each league's configured range (stability modes N/A).

    Args:
        conn: Database connection
        external_occupied: Channel numbers occupied by non-Teamarr channels (#146)
        force_reset: When True (gap/strict only), perform the full re-layout that
            re-grids every channel by priority — the one time existing channels move.

    Returns:
        Dict with statistics: channels_processed, channels_moved, drift_details
    """
    mode = get_global_channel_mode(conn)
    if mode == "manual":
        return _reassign_manual(conn, external_occupied)

    stability = get_channel_stability_settings(conn)
    smode = stability["mode"]
    if smode == "compact":
        return _reassign_auto(conn, external_occupied)

    ext = external_occupied or set()
    if force_reset:
        result = _reassign_reset(conn, smode, stability["gap_size"], ext)
        _mark_channel_reset(conn)
        return result
    return _reassign_sticky(conn, smode, stability["gap_size"], ext)


def _channel_num_as_int(value) -> int | None:
    """Parse a stored channel_number (TEXT) into an int, or None."""
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return None


def _reassign_sticky(
    conn: Connection,
    mode: str,
    gap_size: int,
    ext: set[int],
) -> dict:
    """Sticky placement for gap/strict modes (no full re-layout).

    Locked channels never move. Unlocked channels (newly created, or existing
    channels the first time the mode is active) are assigned a number and locked:

    - gap:    the lowest free number in the channel's sorted neighbourhood
              (between the surrounding locked anchors); reuses freed slots. Falls
              back to appending at the end of the range when the neighbourhood is full.
    - strict: appended to the end of the used range, so nothing existing is displaced.
    """
    range_start, range_end = get_global_channel_range(conn)
    effective_end = range_end if range_end else MAX_CHANNEL

    sorted_channels = get_all_channels_sorted(conn)
    if not sorted_channels:
        return {"channels_processed": 0, "channels_moved": 0, "drift_details": []}

    # Locked anchors (and external channels) occupy their numbers permanently here.
    used: set[int] = set(ext)
    for ch in sorted_channels:
        num = _channel_num_as_int(ch["channel_number"])
        if ch.get("channel_number_locked") and num is not None:
            used.add(num)

    # For gap mode: the next locked anchor's number after each index bounds insertion.
    n = len(sorted_channels)
    next_anchor: list[int | None] = [None] * n
    upcoming: int | None = None
    for i in range(n - 1, -1, -1):
        next_anchor[i] = upcoming
        ch = sorted_channels[i]
        num = _channel_num_as_int(ch["channel_number"])
        if ch.get("channel_number_locked") and num is not None:
            upcoming = num

    def append_to_end() -> int:
        base = max(used) if used else (range_start - 1)
        candidate = max(base + 1, range_start)
        while candidate in used:
            candidate += 1
        return candidate

    drift_details: list[dict] = []
    channels_moved = 0
    lo = range_start - 1  # so the first grid slot considered is range_start

    for i, ch in enumerate(sorted_channels):
        cur = _channel_num_as_int(ch["channel_number"])

        if ch.get("channel_number_locked") and cur is not None:
            lo = cur
            continue

        # Place this unlocked channel.
        if mode == "strict":
            target = append_to_end()
        else:  # gap
            hi = next_anchor[i] if next_anchor[i] is not None else (effective_end + 1)
            candidate = lo + 1
            while candidate in used:
                candidate += 1
            if candidate < hi and candidate <= effective_end:
                target = candidate
            else:
                target = append_to_end()

        if target > effective_end:
            logger.warning(
                "[CHANNEL_SORT] %s sticky stopped at channel %d - range exhausted",
                mode.upper(), ch["id"],
            )
            break

        used.add(target)
        lo = target

        if cur != target:
            conn.execute(
                _SET_NUMBER_LOCKED_SQL,
                (target, ch["id"]),
            )
            drift_details.append({
                "channel_id": ch["id"],
                "dispatcharr_channel_id": ch["dispatcharr_channel_id"],
                "channel_name": ch["channel_name"],
                "old_number": cur,
                "new_number": target,
            })
            channels_moved += 1
            logger.debug(
                "[CHANNEL_NUM] '%s' placed #%s → #%d (%s)",
                ch["channel_name"], cur, target, mode,
            )
        else:
            # Number already correct — just lock it so it's sticky from now on.
            conn.execute(_LOCK_SQL, (ch["id"],))

    logger.info(
        "[CHANNEL_SORT] %s sticky: %d channels processed, %d placed",
        mode.upper(), len(sorted_channels), channels_moved,
    )
    return {
        "channels_processed": len(sorted_channels),
        "channels_moved": channels_moved,
        "drift_details": drift_details,
    }


def _reassign_reset(
    conn: Connection,
    mode: str,
    gap_size: int,
    ext: set[int],
) -> dict:
    """Full re-layout for gap/strict modes (the daily reset window).

    Re-grids every channel by priority order and re-locks them: contiguous for
    strict, spaced by gap_size for gap. This is the only path that moves a
    channel that is already locked.
    """
    range_start, range_end = get_global_channel_range(conn)
    effective_end = range_end if range_end else MAX_CHANNEL
    step = gap_size if (mode == "gap" and gap_size > 0) else 1

    sorted_channels = get_all_channels_sorted(conn)
    if not sorted_channels:
        return {"channels_processed": 0, "channels_moved": 0, "drift_details": []}

    drift_details: list[dict] = []
    channels_moved = 0

    num = range_start
    while num in ext:
        num += 1

    for ch in sorted_channels:
        if num > effective_end:
            logger.warning(
                "[CHANNEL_SORT] %s reset stopped at channel %d - range exhausted",
                mode.upper(), ch["id"],
            )
            break

        cur = _channel_num_as_int(ch["channel_number"])
        if cur != num:
            conn.execute(
                _SET_NUMBER_LOCKED_SQL,
                (num, ch["id"]),
            )
            drift_details.append({
                "channel_id": ch["id"],
                "dispatcharr_channel_id": ch["dispatcharr_channel_id"],
                "channel_name": ch["channel_name"],
                "old_number": cur,
                "new_number": num,
            })
            channels_moved += 1
        else:
            conn.execute(_LOCK_SQL, (ch["id"],))

        num += step
        while num in ext:
            num += 1

    logger.info(
        "[CHANNEL_SORT] %s reset re-layout: %d channels processed, %d moved",
        mode.upper(), len(sorted_channels), channels_moved,
    )
    return {
        "channels_processed": len(sorted_channels),
        "channels_moved": channels_moved,
        "drift_details": drift_details,
    }


def _reassign_auto(
    conn: Connection,
    external_occupied: set[int] | None = None,
) -> dict:
    """Reassign all channels sequentially from range_start by sort order."""
    range_start, range_end = get_global_channel_range(conn)
    effective_end = range_end if range_end else MAX_CHANNEL
    ext_set = external_occupied or set()

    sorted_channels = get_all_channels_sorted(conn)

    if not sorted_channels:
        logger.info("[CHANNEL_SORT] No channels to reassign")
        return {"channels_processed": 0, "channels_moved": 0, "drift_details": []}

    channels_moved = 0
    drift_details = []

    next_num = range_start
    while next_num in ext_set:
        next_num += 1

    for ch in sorted_channels:
        old_num = ch["channel_number"]

        if next_num > effective_end:
            logger.warning(
                "[CHANNEL_SORT] AUTO reassign stopped at channel %d - range exhausted", ch["id"],
            )
            break

        if old_num != next_num:
            conn.execute(
                "UPDATE managed_channels SET channel_number = ? WHERE id = ?",
                (next_num, ch["id"]),
            )
            drift_details.append({
                "channel_id": ch["id"],
                "dispatcharr_channel_id": ch["dispatcharr_channel_id"],
                "channel_name": ch["channel_name"],
                "old_number": old_num,
                "new_number": next_num,
            })
            channels_moved += 1
            logger.debug(
                "[CHANNEL_NUM] '%s' moved #%s → #%d",
                ch["channel_name"], old_num, next_num,
            )

        next_num += 1
        while next_num in ext_set:
            next_num += 1

    logger.info(
        "[CHANNEL_SORT] AUTO reassign: %d channels processed, %d moved",
        len(sorted_channels), channels_moved,
    )

    return {
        "channels_processed": len(sorted_channels),
        "channels_moved": channels_moved,
        "drift_details": drift_details,
    }


def _reassign_manual(
    conn: Connection,
    external_occupied: set[int] | None = None,
) -> dict:
    """Reassign channels in MANUAL mode: sequential within each league's range."""
    league_starts = get_league_channel_starts(conn)
    range_start, range_end = get_global_channel_range(conn)
    effective_end = range_end if range_end else MAX_CHANNEL
    ext_set = external_occupied or set()

    sorted_channels = get_all_channels_sorted(conn)

    if not sorted_channels:
        logger.info("[CHANNEL_SORT] No channels to reassign (manual)")
        return {"channels_processed": 0, "channels_moved": 0, "drift_details": []}

    # Track next available number per league
    league_counters: dict[str, int] = {}
    channels_moved = 0
    drift_details = []

    for ch in sorted_channels:
        old_num = ch["channel_number"]
        league = (ch.get("league") or "").lower()

        if league not in league_counters:
            start = league_starts.get(league, range_start)
            # Skip external channels at the start
            while start in ext_set:
                start += 1
            league_counters[league] = start

        next_num = league_counters[league]
        while next_num in ext_set:
            next_num += 1

        if next_num > effective_end:
            logger.warning(
                "[CHANNEL_SORT] MANUAL reassign stopped for league '%s' - range exhausted", league,
            )
            continue

        if old_num != next_num:
            conn.execute(
                "UPDATE managed_channels SET channel_number = ? WHERE id = ?",
                (next_num, ch["id"]),
            )
            drift_details.append({
                "channel_id": ch["id"],
                "dispatcharr_channel_id": ch["dispatcharr_channel_id"],
                "channel_name": ch["channel_name"],
                "old_number": old_num,
                "new_number": next_num,
            })
            channels_moved += 1
            logger.debug(
                "[CHANNEL_NUM] '%s' moved #%s → #%d",
                ch["channel_name"], old_num, next_num,
            )

        league_counters[league] = next_num + 1

    logger.info(
        "[CHANNEL_SORT] MANUAL reassign: %d channels processed, %d moved",
        len(sorted_channels), channels_moved,
    )

    return {
        "channels_processed": len(sorted_channels),
        "channels_moved": channels_moved,
        "drift_details": drift_details,
    }
