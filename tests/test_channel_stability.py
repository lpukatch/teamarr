"""Tests for channel numbering stability modes (gap / strict) and the daily reset.

Covers the invariants behind stable channel numbers across an event's lifecycle:
- gap:    new channels slot into a free number in their sorted neighbourhood;
          existing (locked) channels never move; freed slots are reused.
- strict: new channels append to the end of the used range so nothing is displaced.
- reset:  the full re-layout (the only time locked channels move) re-grids by priority.
- gating: should_run_channel_reset fires once per day at/after the configured time.
"""

import sqlite3
from datetime import datetime, timedelta

import pytest

from teamarr.database import channel_numbers as cn


@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE settings (
          id INTEGER PRIMARY KEY,
          channel_range_start INTEGER DEFAULT 101,
          channel_range_end INTEGER,
          global_channel_mode TEXT DEFAULT 'auto',
          league_channel_starts TEXT DEFAULT '{}',
          global_consolidation_mode TEXT DEFAULT 'consolidate',
          channel_stability_mode TEXT DEFAULT 'compact',
          channel_gap_size INTEGER DEFAULT 1,
          channel_daily_reset_enabled INTEGER DEFAULT 1,
          channel_daily_reset_time TEXT DEFAULT '04:00',
          last_channel_reset_at TEXT
        );
        CREATE TABLE event_epg_groups (id INTEGER PRIMARY KEY, enabled INTEGER DEFAULT 1);
        CREATE TABLE managed_channels (
          id INTEGER PRIMARY KEY, dispatcharr_channel_id INTEGER, channel_number TEXT,
          channel_number_locked INTEGER DEFAULT 0, channel_name TEXT, event_epg_group_id INTEGER,
          primary_stream_id INTEGER, event_id TEXT, sport TEXT, league TEXT,
          home_team TEXT, away_team TEXT, event_date TEXT, exception_keyword TEXT,
          created_at TEXT, deleted_at TEXT
        );
        CREATE TABLE channel_sort_priorities (
          id INTEGER PRIMARY KEY, sport TEXT, league_code TEXT, sort_priority INTEGER,
          created_at TEXT, updated_at TEXT
        );
        CREATE TABLE channel_priority_teams (id INTEGER PRIMARY KEY, sport TEXT, team_name TEXT);
        INSERT INTO settings (id) VALUES (1);
        """
    )
    return conn


def _add(conn, cid, name, number, locked, event_date, event_id):
    conn.execute(
        """INSERT INTO managed_channels
           (id, channel_name, channel_number, channel_number_locked,
            event_date, event_id, sport, league)
           VALUES (?, ?, ?, ?, ?, ?, 'football', 'nfl')""",
        (cid, name, number, locked, event_date, event_id),
    )


def _numbers(conn):
    rows = conn.execute(
        "SELECT channel_name, channel_number FROM managed_channels "
        "WHERE deleted_at IS NULL ORDER BY CAST(channel_number AS INT)"
    ).fetchall()
    return {r["channel_name"]: int(r["channel_number"]) for r in rows}


def _set_mode(conn, mode, gap=1):
    conn.execute(
        "UPDATE settings SET channel_stability_mode = ?, channel_gap_size = ?",
        (mode, gap),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# gap mode
# ---------------------------------------------------------------------------


def test_gap_new_channel_slots_into_neighbourhood(db):
    _set_mode(db, "gap", gap=3)
    _add(db, 1, "A", "101", 1, "2026-06-18 10:00:00", "e1")
    _add(db, 2, "B", "104", 1, "2026-06-18 12:00:00", "e2")
    # New channel sorts (by time) between A and B; provisional number is irrelevant.
    _add(db, 3, "NEW", "500", 0, "2026-06-18 11:00:00", "e3")
    db.commit()

    cn.reassign_all_channels(db)
    nums = _numbers(db)
    assert nums["A"] == 101  # locked, unmoved
    assert nums["B"] == 104  # locked, unmoved
    assert 101 < nums["NEW"] < 104  # slotted into the gap


def test_gap_reuses_freed_slot(db):
    _set_mode(db, "gap", gap=3)
    _add(db, 1, "A", "101", 1, "2026-06-18 10:00:00", "e1")
    _add(db, 2, "B", "104", 1, "2026-06-18 12:00:00", "e2")
    db.commit()
    # A ends → its slot (101) is freed; a new earliest event should reclaim it.
    db.execute("UPDATE managed_channels SET deleted_at = 'x' WHERE id = 1")
    _add(db, 3, "NEW", "500", 0, "2026-06-18 09:00:00", "e3")
    db.commit()

    cn.reassign_all_channels(db)
    nums = _numbers(db)
    assert nums["NEW"] == 101
    assert nums["B"] == 104  # untouched


def test_gap_locked_channels_never_move_on_sticky(db):
    _set_mode(db, "gap", gap=3)
    _add(db, 1, "A", "101", 1, "2026-06-18 10:00:00", "e1")
    _add(db, 2, "B", "104", 1, "2026-06-18 12:00:00", "e2")
    db.commit()
    result = cn.reassign_all_channels(db)
    assert result["channels_moved"] == 0
    assert _numbers(db) == {"A": 101, "B": 104}


# ---------------------------------------------------------------------------
# strict mode
# ---------------------------------------------------------------------------


def test_strict_new_channel_appends_to_end(db):
    _set_mode(db, "strict")
    _add(db, 1, "A", "101", 1, "2026-06-18 10:00:00", "e1")
    _add(db, 2, "B", "102", 1, "2026-06-18 12:00:00", "e2")
    # New event sorts FIRST by time, but strict must append it to the end.
    _add(db, 3, "NEW", "500", 0, "2026-06-18 08:00:00", "e3")
    db.commit()

    cn.reassign_all_channels(db)
    nums = _numbers(db)
    assert nums["A"] == 101
    assert nums["B"] == 102
    assert nums["NEW"] == 103  # appended, did not displace A/B


# ---------------------------------------------------------------------------
# daily reset
# ---------------------------------------------------------------------------


def test_reset_relayout_regrids_by_priority(db):
    _set_mode(db, "gap", gap=3)
    # Out-of-order numbers; reset should re-grid by event time at 101, 104, 107.
    _add(db, 1, "A", "120", 1, "2026-06-18 10:00:00", "e1")
    _add(db, 2, "B", "101", 1, "2026-06-18 12:00:00", "e2")
    _add(db, 3, "C", "150", 1, "2026-06-18 14:00:00", "e3")
    db.commit()

    cn.reassign_all_channels(db, force_reset=True)
    nums = _numbers(db)
    assert nums == {"A": 101, "B": 104, "C": 107}
    # Reset stamps last_channel_reset_at so the daily gate closes.
    stamp = db.execute("SELECT last_channel_reset_at FROM settings WHERE id = 1").fetchone()[0]
    assert stamp is not None


def test_strict_reset_is_contiguous(db):
    _set_mode(db, "strict")
    _add(db, 1, "A", "120", 1, "2026-06-18 10:00:00", "e1")
    _add(db, 2, "B", "101", 1, "2026-06-18 12:00:00", "e2")
    db.commit()
    cn.reassign_all_channels(db, force_reset=True)
    assert _numbers(db) == {"A": 101, "B": 102}


# ---------------------------------------------------------------------------
# reset gating
# ---------------------------------------------------------------------------


def test_compact_mode_never_resets(db):
    _set_mode(db, "compact")
    assert cn.should_run_channel_reset(db) is False
    assert cn.is_sticky_mode(db) is False


def test_reset_fires_first_run_after_window(db):
    _set_mode(db, "gap", gap=3)
    db.execute("UPDATE settings SET channel_daily_reset_time = '00:00'")  # always passed today
    db.commit()
    # No prior reset → should fire.
    assert cn.should_run_channel_reset(db) is True


def test_reset_does_not_refire_same_day(db):
    _set_mode(db, "gap", gap=3)
    db.execute("UPDATE settings SET channel_daily_reset_time = '00:00'")
    # Already reset earlier today.
    db.execute(
        "UPDATE settings SET last_channel_reset_at = ?",
        (datetime.now().isoformat(),),
    )
    db.commit()
    assert cn.should_run_channel_reset(db) is False


def test_reset_refires_next_day(db):
    _set_mode(db, "gap", gap=3)
    db.execute("UPDATE settings SET channel_daily_reset_time = '00:00'")
    db.execute(
        "UPDATE settings SET last_channel_reset_at = ?",
        ((datetime.now() - timedelta(days=1)).isoformat(),),
    )
    db.commit()
    assert cn.should_run_channel_reset(db) is True


def test_reset_disabled_never_fires(db):
    _set_mode(db, "gap", gap=3)
    db.execute(
        "UPDATE settings SET channel_daily_reset_time = '00:00', "
        "channel_daily_reset_enabled = 0"
    )
    db.commit()
    assert cn.should_run_channel_reset(db) is False


def test_sticky_mode_detection(db):
    _set_mode(db, "gap")
    assert cn.is_sticky_mode(db) is True
    _set_mode(db, "strict")
    assert cn.is_sticky_mode(db) is True
    # Manual global mode overrides stability (per-league sequential).
    db.execute("UPDATE settings SET global_channel_mode = 'manual'")
    db.commit()
    assert cn.is_sticky_mode(db) is False
