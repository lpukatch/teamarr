"""Tests for the stream -> EPG-source tvg_id resolver (epic teamarrv2-183).

Covers the precedence cascade (direct tvg_id > curated channel > strict name)
and the strict-name guardrails that keep "ESPN" from resolving to "ESPN2".
"""

from teamarr.consumers.matching.epg_resolver import (
    normalize_channel_name,
    resolve_program_tvg_ids,
)


def _epgdata(rows):
    """rows: list of (id, tvg_id, name)."""
    return [{"id": i, "tvg_id": t, "name": n} for i, t, n in rows]


# ================================================================ normalization


def test_normalize_strips_quality_and_punctuation():
    assert normalize_channel_name("beIn Sports Xtra FHD") == "bein sports xtra"
    assert normalize_channel_name("Willow 2 HD") == "willow 2"
    assert normalize_channel_name("World Fishing Network HD (US)") == "world fishing network"


def test_normalize_keeps_distinguishing_digits():
    # ESPN vs ESPN2 must stay distinct after normalization
    assert normalize_channel_name("ESPN HD") != normalize_channel_name("ESPN2 HD")
    assert normalize_channel_name("ESPN2 HD") == "espn2"


def test_normalize_does_not_drop_identity_words():
    # "USA" is identity here, not a quality tag — must survive
    assert normalize_channel_name("USA Network HD") == "usa network"


# ====================================================================== cascade


def test_direct_tvg_id_match_wins():
    streams = [{"id": 1, "name": "Whatever", "tvg_id": "82547"}]
    epg = _epgdata([(100, "82547", "FS1 HD")])
    res, stats = resolve_program_tvg_ids(streams, epg, {})
    assert res == {"82547": "82547"}
    assert stats["direct"] == 1


def test_channel_outranks_name():
    # Stream name would name-match "FS1 HD" (tvg 82547), but the curated channel
    # points at a different EPGData row — the channel must win.
    streams = [{"id": 7, "name": "FS1 HD", "tvg_id": "FoxSports1.us"}]
    epg = _epgdata([(100, "82547", "FS1 HD"), (200, "99999", "FS1 Regional")])
    stream_channels = {7: {"epg_data_id": 200}}
    res, stats = resolve_program_tvg_ids(streams, epg, stream_channels)
    assert res == {"FoxSports1.us": "99999"}
    assert stats["channel"] == 1
    assert stats["name"] == 0


def test_name_match_used_when_no_channel():
    streams = [{"id": 7, "name": "beIn Sports Xtra FHD", "tvg_id": "beINSportsXtra.us"}]
    epg = _epgdata([(100, "113143", "beIn Sports Xtra")])
    res, stats = resolve_program_tvg_ids(streams, epg, {})
    assert res == {"beINSportsXtra.us": "113143"}
    assert stats["name"] == 1


def test_ambiguous_name_is_skipped():
    # Two EPGData rows normalize to the same name but have different tvg_ids →
    # ambiguous → no resolution (don't guess).
    streams = [{"id": 7, "name": "Sky Sports HD", "tvg_id": "sky.us"}]
    epg = _epgdata([(1, "aaa", "Sky Sports"), (2, "bbb", "Sky Sports FHD")])
    res, stats = resolve_program_tvg_ids(streams, epg, {})
    assert res == {}
    assert stats["ambiguous_name"] == 1
    assert stats["unresolved"] == 1


def test_espn_does_not_resolve_to_espn2():
    streams = [{"id": 7, "name": "ESPN HD", "tvg_id": "espn.us"}]
    epg = _epgdata([(1, "espn2id", "ESPN2 HD")])
    res, _ = resolve_program_tvg_ids(streams, epg, {})
    assert res == {}


def test_effective_epg_data_id_preferred_over_base():
    streams = [{"id": 7, "name": "X", "tvg_id": "x.us"}]
    epg = _epgdata([(10, "base", "A"), (20, "override", "B")])
    stream_channels = {7: {"epg_data_id": 10, "effective_epg_data_id": 20}}
    res, _ = resolve_program_tvg_ids(streams, epg, stream_channels)
    assert res == {"x.us": "override"}


def test_unresolved_when_nothing_matches():
    streams = [{"id": 7, "name": "Totally Unknown Channel", "tvg_id": "unk.us"}]
    epg = _epgdata([(1, "82547", "FS1 HD")])
    res, stats = resolve_program_tvg_ids(streams, epg, {})
    assert res == {}
    assert stats["unresolved"] == 1


def test_streams_without_tvg_id_are_ignored():
    streams = [{"id": 7, "name": "FS1 HD", "tvg_id": ""}]
    epg = _epgdata([(100, "82547", "FS1 HD")])
    res, _ = resolve_program_tvg_ids(streams, epg, {})
    assert res == {}


def test_first_stream_wins_for_shared_tvg_id():
    streams = [
        {"id": 1, "name": "FS1 HD", "tvg_id": "dup.us"},
        {"id": 2, "name": "Other", "tvg_id": "dup.us"},
    ]
    epg = _epgdata([(100, "82547", "FS1 HD")])
    res, _ = resolve_program_tvg_ids(streams, epg, {})
    assert res == {"dup.us": "82547"}
