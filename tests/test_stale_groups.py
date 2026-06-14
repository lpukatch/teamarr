"""Stale source-group detection (lylt.1).

A group is stale when its Dispatcharr M3U source channel-group no longer
exists. Off-season (group still exists, zero streams) must NOT be flagged, and
a Dispatcharr blip (empty/failed group list) must flag nothing.
"""

import contextlib
import sqlite3
from pathlib import Path
from types import SimpleNamespace

from teamarr.consumers.reconciliation import detect_stale_groups

SCHEMA = Path(__file__).resolve().parents[1] / "teamarr" / "database" / "schema.sql"


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA.read_text())
    return conn


def _factory(conn: sqlite3.Connection):
    @contextlib.contextmanager
    def factory():
        yield conn
        conn.commit()

    return factory


def _add_group(conn, name, m3u_group_id, *, enabled=1, is_channel_source=0):
    conn.execute(
        "INSERT INTO event_epg_groups (name, leagues, m3u_group_id, enabled, is_channel_source) "
        "VALUES (?, '[]', ?, ?, ?)",
        (name, m3u_group_id, enabled, is_channel_source),
    )
    conn.commit()


def _patch_dispatcharr(monkeypatch, group_ids):
    """Fake get_dispatcharr_connection -> .m3u.list_groups() yields ids."""
    import teamarr.dispatcharr.factory as factory

    fake = SimpleNamespace(
        m3u=SimpleNamespace(list_groups=lambda: [SimpleNamespace(id=i) for i in group_ids])
    )
    monkeypatch.setattr(factory, "get_dispatcharr_connection", lambda db_factory=None: fake)


def test_missing_source_is_flagged(monkeypatch):
    conn = _db()
    _add_group(conn, "Live Group", 10)
    _add_group(conn, "Gone Group", 99)
    _patch_dispatcharr(monkeypatch, [10, 20, 30])  # 99 is gone

    stale = detect_stale_groups(_factory(conn))

    assert {g["name"] for g in stale} == {"Gone Group"}
    live = conn.execute(
        "SELECT source_missing, source_last_seen FROM event_epg_groups WHERE name='Live Group'"
    ).fetchone()
    assert live["source_missing"] == 0
    assert live["source_last_seen"] is not None  # present source refreshed
    gone = conn.execute(
        "SELECT source_missing FROM event_epg_groups WHERE name='Gone Group'"
    ).fetchone()
    assert gone["source_missing"] == 1


def test_channel_source_group_excluded(monkeypatch):
    conn = _db()
    _add_group(conn, "System Source", 99, is_channel_source=1)
    _patch_dispatcharr(monkeypatch, [10])
    assert detect_stale_groups(_factory(conn)) == []


def test_group_without_m3u_source_skipped(monkeypatch):
    conn = _db()
    _add_group(conn, "League Only", None)
    _patch_dispatcharr(monkeypatch, [10])
    assert detect_stale_groups(_factory(conn)) == []


def test_empty_group_list_flags_nothing(monkeypatch):
    """A connection blip (no groups returned) must not flag everything stale."""
    conn = _db()
    _add_group(conn, "Gone Group", 99)
    _patch_dispatcharr(monkeypatch, [])

    assert detect_stale_groups(_factory(conn)) == []
    row = conn.execute(
        "SELECT source_missing FROM event_epg_groups WHERE name='Gone Group'"
    ).fetchone()
    assert row["source_missing"] == 0


def test_list_groups_error_flags_nothing(monkeypatch):
    conn = _db()
    _add_group(conn, "Gone Group", 99)

    import teamarr.dispatcharr.factory as factory

    def boom():
        raise RuntimeError("dispatcharr down")

    fake = SimpleNamespace(m3u=SimpleNamespace(list_groups=boom))
    monkeypatch.setattr(factory, "get_dispatcharr_connection", lambda db_factory=None: fake)

    assert detect_stale_groups(_factory(conn)) == []


def test_recovery_clears_stale_flag(monkeypatch):
    """Once the source reappears, the group is no longer stale."""
    conn = _db()
    _add_group(conn, "Flaky Group", 99)

    _patch_dispatcharr(monkeypatch, [10])  # gone
    assert {g["name"] for g in detect_stale_groups(_factory(conn))} == {"Flaky Group"}

    _patch_dispatcharr(monkeypatch, [99])  # back
    assert detect_stale_groups(_factory(conn)) == []
    row = conn.execute(
        "SELECT source_missing FROM event_epg_groups WHERE name='Flaky Group'"
    ).fetchone()
    assert row["source_missing"] == 0
