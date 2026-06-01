"""Tests for time-windowed stream membership (teamarrv2-183.5).

Covers compute_stream_window() and the window-aware active set returned by
get_ordered_stream_ids() — the mechanism that lets one linear stream rotate
across event channels, attached only during its EPG program slot.
"""

import sqlite3
from datetime import UTC, datetime, timedelta, timezone

import pytest

from teamarr.consumers.lifecycle.timing import compute_stream_window
from teamarr.database.channels.streams import get_ordered_stream_ids

BASE = datetime(2026, 6, 1, 18, 0, 0, tzinfo=UTC)


# ============================================================ compute_stream_window


def test_window_none_for_no_program_slot():
    assert compute_stream_window(None, None, 60, 60) == (None, None)
    assert compute_stream_window(BASE, None, 60, 60) == (None, None)
    assert compute_stream_window(None, BASE, 60, 60) == (None, None)


def test_window_applies_buffers_and_formats_sqlite_utc():
    start = BASE  # 18:00
    end = BASE + timedelta(hours=3)  # 21:00
    attach, detach = compute_stream_window(start, end, 60, 30)
    assert attach == "2026-06-01 17:00:00"  # 18:00 - 60m
    assert detach == "2026-06-01 21:30:00"  # 21:00 + 30m


def test_window_converts_to_utc():
    est = datetime(2026, 6, 1, 13, 0, 0, tzinfo=timezone(timedelta(hours=-5)))
    # 13:00 EST == 18:00 UTC
    attach, detach = compute_stream_window(est, est + timedelta(hours=1), 0, 0)
    assert attach == "2026-06-01 18:00:00"
    assert detach == "2026-06-01 19:00:00"


def test_window_zero_buffers():
    attach, detach = compute_stream_window(BASE, BASE + timedelta(hours=2), 0, 0)
    assert attach == "2026-06-01 18:00:00"
    assert detach == "2026-06-01 20:00:00"


# ======================================================== get_ordered_stream_ids gating


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.execute(
        """CREATE TABLE managed_channel_streams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            managed_channel_id INTEGER,
            dispatcharr_stream_id INTEGER,
            priority INTEGER DEFAULT 0,
            added_at TEXT DEFAULT CURRENT_TIMESTAMP,
            removed_at TEXT,
            attach_at TEXT,
            detach_at TEXT
        )"""
    )
    return c


def _add(conn, stream_id, priority=0, attach_at=None, detach_at=None, removed_at=None):
    conn.execute(
        "INSERT INTO managed_channel_streams "
        "(managed_channel_id, dispatcharr_stream_id, priority, attach_at, detach_at, removed_at) "
        "VALUES (1, ?, ?, ?, ?, ?)",
        (stream_id, priority, attach_at, detach_at, removed_at),
    )
    conn.commit()


def test_null_window_always_active(conn):
    _add(conn, 100)  # full-life, no window
    assert get_ordered_stream_ids(conn, 1, now="2026-06-01 18:00:00") == [100]
    # active regardless of when "now" is
    assert get_ordered_stream_ids(conn, 1, now="2030-01-01 00:00:00") == [100]


def test_in_window_stream_active(conn):
    _add(conn, 200, attach_at="2026-06-01 17:00:00", detach_at="2026-06-01 21:00:00")
    assert get_ordered_stream_ids(conn, 1, now="2026-06-01 18:00:00") == [200]


def test_before_window_excluded(conn):
    _add(conn, 200, attach_at="2026-06-01 17:00:00", detach_at="2026-06-01 21:00:00")
    assert get_ordered_stream_ids(conn, 1, now="2026-06-01 16:59:00") == []


def test_after_window_excluded(conn):
    _add(conn, 200, attach_at="2026-06-01 17:00:00", detach_at="2026-06-01 21:00:00")
    # half-open window: detach_at itself is excluded
    assert get_ordered_stream_ids(conn, 1, now="2026-06-01 21:00:00") == []


def test_attach_boundary_inclusive(conn):
    _add(conn, 200, attach_at="2026-06-01 17:00:00", detach_at="2026-06-01 21:00:00")
    assert get_ordered_stream_ids(conn, 1, now="2026-06-01 17:00:00") == [200]


def test_removed_stream_never_active(conn):
    _add(conn, 200, attach_at="2026-06-01 17:00:00", detach_at="2026-06-01 21:00:00",
         removed_at="2026-06-01 17:30:00")
    assert get_ordered_stream_ids(conn, 1, now="2026-06-01 18:00:00") == []


def test_mixed_streams_only_in_window_plus_fulllife(conn):
    # ESPN rotating: full-life dedicated stream + a windowed linear stream
    _add(conn, 100, priority=0)  # dedicated, always on
    _add(conn, 200, priority=1, attach_at="2026-06-01 17:00:00", detach_at="2026-06-01 21:00:00")
    _add(conn, 300, priority=2, attach_at="2026-06-01 23:00:00", detach_at="2026-06-02 02:00:00")
    # at 18:00 only 100 (full-life) + 200 (in window); 300 is later
    assert get_ordered_stream_ids(conn, 1, now="2026-06-01 18:00:00") == [100, 200]
    # at 23:30 only 100 + 300
    assert get_ordered_stream_ids(conn, 1, now="2026-06-01 23:30:00") == [100, 300]


def test_priority_order_preserved(conn):
    _add(conn, 300, priority=2)
    _add(conn, 100, priority=0)
    _add(conn, 200, priority=1)
    assert get_ordered_stream_ids(conn, 1, now="2026-06-01 18:00:00") == [100, 200, 300]
