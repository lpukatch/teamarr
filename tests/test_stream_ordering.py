"""Tests for StreamOrderingService.

Covers the additive scoring engine (a stream's score is the sum of the points
of every rule it matches — not first-match-wins), plus the regex-heavy rule
types from PR #216 (team_feed / not_team_feed feed detection, the stream_type
team filter), and the team-term builder and key parsing.
"""

import pytest

from teamarr.database.channels.types import ManagedChannelStream
from teamarr.database.connection import get_connection, get_db, init_db
from teamarr.database.settings.types import StreamOrderingRule
from teamarr.services.stream_ordering import StreamOrderingService


def _stream(name: str | None = None, match_type: str = "event") -> ManagedChannelStream:
    return ManagedChannelStream(
        id=1,
        managed_channel_id=1,
        dispatcharr_stream_id=1,
        stream_name=name,
        match_type=match_type,
    )


@pytest.fixture
def seeded_db(tmp_path, monkeypatch):
    """Fresh DB seeded with a few teams in team_cache and the teams table."""
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_PATH", str(db_path))
    init_db()
    with get_db() as conn:
        conn.executemany(
            """
            INSERT OR REPLACE INTO team_cache
            (team_name, team_abbrev, team_short_name, provider, provider_team_id, league, sport)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                ("Pittsburgh Pirates", "PIT", "Pirates", "espn", "23", "mlb", "baseball"),
                ("Chicago Cubs", "CHC", "Cubs", "espn", "16", "mlb", "baseball"),
                ("Cincinnati Reds", "CIN", "Reds", "espn", "17", "mlb", "baseball"),
            ],
        )
        conn.commit()

    conn = get_connection()
    yield conn
    conn.close()


# ---------------------------------------------------------------------------
# Existing rule types still work
# ---------------------------------------------------------------------------


class TestBasicRules:
    def test_regex_match(self):
        svc = StreamOrderingService([StreamOrderingRule("regex", r"(?i)1080p", 10)])
        assert svc.compute_score(_stream("ESPN 1080p")) == 10
        assert svc.compute_score(_stream("ESPN 720p")) == 0

    def test_m3u_match_case_insensitive(self):
        svc = StreamOrderingService([StreamOrderingRule("m3u", "Premium IPTV", 10)])
        s = _stream("anything")
        s.m3u_account_name = "premium iptv"
        assert svc.compute_score(s) == 10

    def test_matching_rules_add_up(self):
        rules = [
            StreamOrderingRule("regex", r"(?i)1080p", 20),
            StreamOrderingRule("regex", r"(?i)espn", 10),
        ]
        svc = StreamOrderingService(rules)
        # Both rules match "ESPN 1080p" — their points sum.
        assert svc.compute_score(_stream("ESPN 1080p")) == 30
        # Only the ESPN rule matches this one.
        assert svc.compute_score(_stream("ESPN 720p")) == 10
        # Neither matches.
        assert svc.compute_score(_stream("Fox 720p")) == 0

    def test_negative_points_deprioritize(self):
        rules = [
            StreamOrderingRule("m3u", "Provider A", 10),
            StreamOrderingRule("regex", r"(?i)backup", -50),
        ]
        svc = StreamOrderingService(rules)
        s = _stream("Backup Feed")
        s.m3u_account_name = "Provider A"
        assert svc.compute_score(s) == -40


# ---------------------------------------------------------------------------
# The worked example from the Stream Priority docs: quality can outrank a
# provider preference without any rule reordering, because points add up.
# ---------------------------------------------------------------------------


class TestQualityOverridesProviderExample:
    def _svc(self):
        return StreamOrderingService([
            StreamOrderingRule("m3u", "Provider A", 10),
            StreamOrderingRule("stats_metric", "resolution_height|>=|1080", 20),
        ])

    def _stream(self, account: str, resolution: str) -> ManagedChannelStream:
        s = ManagedChannelStream(
            id=1, managed_channel_id=1, dispatcharr_stream_id=1,
            stream_stats={"resolution": resolution},
        )
        s.m3u_account_name = account
        return s

    def test_scores_match_worked_example(self):
        svc = self._svc()
        a_1080 = self._stream("Provider A", "1920x1080")
        b_1080 = self._stream("Provider B", "1920x1080")
        a_720 = self._stream("Provider A", "1280x720")
        b_720 = self._stream("Provider B", "1280x720")

        assert svc.compute_score(a_1080) == 30
        assert svc.compute_score(b_1080) == 20
        assert svc.compute_score(a_720) == 10
        assert svc.compute_score(b_720) == 0

        ordered = svc.sort_streams([b_720, a_720, b_1080, a_1080])
        assert ordered == [a_1080, b_1080, a_720, b_720]


# ---------------------------------------------------------------------------
# epg_match rule (epic 183 — EPG program-data matched streams)
# ---------------------------------------------------------------------------


class TestEPGMatch:
    def _epg_stream(self, match_method):
        return ManagedChannelStream(
            id=1, managed_channel_id=1, dispatcharr_stream_id=1,
            stream_name="ESPN", match_method=match_method,
        )

    def test_epg_match_matches_epg_method(self):
        svc = StreamOrderingService([StreamOrderingRule("epg_match", "", 10)])
        assert svc.compute_score(self._epg_stream("epg")) == 10

    def test_epg_match_ignores_other_methods(self):
        svc = StreamOrderingService([StreamOrderingRule("epg_match", "", 10)])
        assert svc.compute_score(self._epg_stream("fuzzy")) == 0
        assert svc.compute_score(self._epg_stream(None)) == 0


class TestDispatcharrGroup:
    def _stream(self, dp_group):
        return ManagedChannelStream(
            id=1, managed_channel_id=1, dispatcharr_stream_id=1,
            stream_name="ESPN", dispatcharr_channel_group=dp_group,
        )

    def test_matches_dispatcharr_group_case_insensitive(self):
        svc = StreamOrderingService([StreamOrderingRule("dispatcharr_group", "US Sports", 10)])
        assert svc.compute_score(self._stream("us sports")) == 10

    def test_ignores_other_group(self):
        svc = StreamOrderingService([StreamOrderingRule("dispatcharr_group", "US Sports", 10)])
        assert svc.compute_score(self._stream("UK Sports")) == 0

    def test_non_channel_source_stream_never_matches(self):
        # Streams without a DP channel group (normal M3U-matched streams) never match.
        svc = StreamOrderingService([StreamOrderingRule("dispatcharr_group", "US Sports", 10)])
        assert svc.compute_score(self._stream(None)) == 0


# ---------------------------------------------------------------------------
# Team-term builder (+ stopword guard)
# ---------------------------------------------------------------------------


class TestBuildTeamTerms:
    def test_extracts_words_city_and_abbrev(self):
        svc = StreamOrderingService([])
        rows = [{"team_name": "Pittsburgh Pirates", "team_abbrev": "PIT"}]
        terms = {t.replace("\\", "") for t in svc._build_team_terms(rows)}
        assert terms == {"Pittsburgh", "Pirates", "PIT"}

    def test_multiword_city_term(self):
        svc = StreamOrderingService([])
        rows = [{"team_name": "New York Yankees", "team_abbrev": "NYY"}]
        terms = {t.replace("\\", "") for t in svc._build_team_terms(rows)}
        # "New" is dropped (<3? no, 3 chars) — actually kept; city = "New York"
        assert "New York" in terms
        assert "Yankees" in terms
        assert "NYY" in terms

    def test_short_words_excluded(self):
        svc = StreamOrderingService([])
        rows = [{"team_name": "FC Bayern", "team_abbrev": "B"}]
        terms = {t.replace("\\", "") for t in svc._build_team_terms(rows)}
        # "FC" (2 chars) excluded as word; "B" (1 char) excluded as abbrev
        assert "Bayern" in terms
        assert "FC" not in terms
        assert "B" not in terms

    def test_stopwords_dropped(self):
        svc = StreamOrderingService([])
        rows = [{"team_name": "The Strongest", "team_abbrev": "STR"}]
        terms = {t.replace("\\", "") for t in svc._build_team_terms(rows)}
        assert "the" not in {t.lower() for t in terms}
        assert "Strongest" in terms


# ---------------------------------------------------------------------------
# team_feed / not_team_feed
# ---------------------------------------------------------------------------


class TestTeamFeed:
    KEY = "espn:mlb:23"  # Pittsburgh Pirates

    @pytest.mark.parametrize(
        "name,expected",
        [
            ("Cubs vs Pirates (Home)", True),
            ("Pirates vs Cubs (Away)", True),
            ("Pirates @ Cubs Away", True),
            ("(Pirates feed) MLB", True),
            ("Home Feed: Cubs vs Pirates", True),
            ("Away Feed: Pirates vs Cubs", True),
            ("Pirates vs Cubs", False),  # no directional marker
            ("Cubs vs Reds (Home)", False),  # different team's feed
            ("ESPN National Feed", False),  # generic, no team
        ],
    )
    def test_team_feed_matching(self, seeded_db, name, expected):
        svc = StreamOrderingService([StreamOrderingRule("team_feed", self.KEY, 10)], seeded_db)
        assert svc.compute_score(_stream(name)) == (10 if expected else 0)

    def test_not_team_feed_inverts_only_feed_marked_streams(self, seeded_db):
        svc = StreamOrderingService([StreamOrderingRule("not_team_feed", self.KEY, 10)], seeded_db)
        # Feed-marked, NOT pirates → matches
        assert svc.compute_score(_stream("Cubs vs Reds (Home)")) == 10
        # Pirates' own feed → does NOT match
        assert svc.compute_score(_stream("Pirates vs Cubs (Away)")) == 0
        # No feed marker at all → gated out, does NOT match
        assert svc.compute_score(_stream("Generic National stream")) == 0

    def test_empty_value_is_noop(self, seeded_db):
        svc = StreamOrderingService([StreamOrderingRule("team_feed", "", 10)], seeded_db)
        assert svc.compute_score(_stream("Pirates vs Cubs (Away)")) == 0

    def test_legacy_integer_id_path(self, seeded_db):
        # The teams table is seeded with demo teams; id=4 is the Detroit Tigers.
        # The legacy team_feed path resolves integer IDs against the teams table.
        svc = StreamOrderingService([StreamOrderingRule("team_feed", "4", 10)], seeded_db)
        assert svc.compute_score(_stream("Cubs vs Tigers (Home)")) == 10
        assert svc.compute_score(_stream("Cubs vs Pirates (Home)")) == 0

    def test_pattern_is_cached(self, seeded_db):
        svc = StreamOrderingService([StreamOrderingRule("team_feed", self.KEY, 10)], seeded_db)
        svc.compute_score(_stream("Cubs vs Pirates (Home)"))
        assert self.KEY in svc._team_feed_patterns

    def test_no_connection_degrades_gracefully(self):
        svc = StreamOrderingService([StreamOrderingRule("team_feed", "espn:mlb:23", 10)], conn=None)
        assert svc.compute_score(_stream("Cubs vs Pirates (Home)")) == 0


# ---------------------------------------------------------------------------
# stream_type with optional team filter
# ---------------------------------------------------------------------------


class TestStreamTypeFilter:
    def test_plain_stream_type_no_filter(self, seeded_db):
        svc = StreamOrderingService([StreamOrderingRule("stream_type", "team", 10)], seeded_db)
        assert svc.compute_score(_stream("anything", match_type="team")) == 10
        assert svc.compute_score(_stream("anything", match_type="event")) == 0

    def test_team_filter_narrows_to_selected_team(self, seeded_db):
        rule = StreamOrderingRule("stream_type", "team|espn:mlb:23", 10)
        svc = StreamOrderingService([rule], seeded_db)
        # team-type stream naming the Pirates → matches
        assert svc.compute_score(_stream("Pirates Network", match_type="team")) == 10
        # team-type stream naming a different team → no match
        assert svc.compute_score(_stream("Cubs Network", match_type="team")) == 0

    def test_team_filter_requires_correct_stream_type(self, seeded_db):
        rule = StreamOrderingRule("stream_type", "team|espn:mlb:23", 10)
        svc = StreamOrderingService([rule], seeded_db)
        # right team name but event-type → stream_type mismatch
        s = _stream("Pirates Network", match_type="event")
        assert svc.compute_score(s) == 0

    def test_empty_team_filter_matches_all_team_streams(self, seeded_db):
        svc = StreamOrderingService([StreamOrderingRule("stream_type", "team|", 10)], seeded_db)
        assert svc.compute_score(_stream("Cubs Network", match_type="team")) == 10


# ---------------------------------------------------------------------------
# Key parsing (2-part vs 3-part)
# ---------------------------------------------------------------------------


class TestKeyParsing:
    def test_two_part_legacy_key(self, seeded_db):
        svc = StreamOrderingService([], seeded_db)
        rows = svc._query_team_cache_by_keys(["espn:23"])
        names = {r["team_name"] for r in rows}
        assert "Pittsburgh Pirates" in names

    def test_three_part_key(self, seeded_db):
        svc = StreamOrderingService([], seeded_db)
        rows = svc._query_team_cache_by_keys(["espn:mlb:23"])
        names = {r["team_name"] for r in rows}
        assert "Pittsburgh Pirates" in names

    def test_mixed_keys(self, seeded_db):
        svc = StreamOrderingService([], seeded_db)
        rows = svc._query_team_cache_by_keys(["espn:23", "espn:mlb:16"])
        names = {r["team_name"] for r in rows}
        assert {"Pittsburgh Pirates", "Chicago Cubs"} <= names


class TestStatsMetric:
    """The stats_metric rule matches streams by Dispatcharr stream_stats values."""

    def _stream(self, stats: dict | None) -> ManagedChannelStream:
        return ManagedChannelStream(
            id=1, managed_channel_id=1, dispatcharr_stream_id=1, stream_stats=stats
        )

    def _svc(self, value: str) -> StreamOrderingService:
        return StreamOrderingService([StreamOrderingRule("stats_metric", value, 10)])

    @pytest.mark.parametrize(
        "operator,threshold,bitrate,expected",
        [
            (">=", "4000", 4000, True),
            (">=", "4000", 3999, False),
            ("<=", "4000", 4000, True),
            ("<=", "4000", 4001, False),
            (">", "4000", 4001, True),
            (">", "4000", 4000, False),
            ("<", "4000", 3999, True),
            ("<", "4000", 4000, False),
            ("=", "4000", 4000, True),
            ("=", "4000", 4001, False),
        ],
    )
    def test_operators(self, operator, threshold, bitrate, expected):
        svc = self._svc(f"ffmpeg_output_bitrate|{operator}|{threshold}")
        stream = self._stream({"ffmpeg_output_bitrate": bitrate})
        matched = svc.compute_score(stream) == 10
        assert matched is expected

    def test_virtual_resolution_width_and_height(self):
        stream = self._stream({"resolution": "1920x1080"})
        assert self._svc("resolution_width|>=|1920").compute_score(stream) == 10
        assert self._svc("resolution_height|>=|1080").compute_score(stream) == 10
        assert self._svc("resolution_width|>|1920").compute_score(stream) == 0

    def test_malformed_resolution_does_not_match(self):
        stream = self._stream({"resolution": "1080"})  # no "x"
        assert self._svc("resolution_width|>=|720").compute_score(stream) == 0

    def test_multi_condition_and(self):
        rule = "source_fps|>=|50;ffmpeg_output_bitrate|>=|4000"
        both = self._stream({"source_fps": 60, "ffmpeg_output_bitrate": 5000})
        one = self._stream({"source_fps": 30, "ffmpeg_output_bitrate": 5000})
        assert self._svc(rule).compute_score(both) == 10
        assert self._svc(rule).compute_score(one) == 0

    def test_is_unknown_matches_when_absent(self):
        # No stats at all, or the specific metric missing → is_unknown matches.
        assert self._svc("source_fps|is_unknown").compute_score(self._stream(None)) == 10
        assert (
            self._svc("source_fps|is_unknown").compute_score(
                self._stream({"resolution": "1920x1080"})
            )
            == 10
        )
        # Metric present → is_unknown does not match.
        assert (
            self._svc("source_fps|is_unknown").compute_score(self._stream({"source_fps": 60}))
            == 0
        )

    def test_numeric_op_with_no_stats_does_not_match(self):
        svc = self._svc("source_fps|>=|50")
        assert svc.compute_score(self._stream(None)) == 0

    def test_malformed_rule_value_does_not_raise(self):
        stream = self._stream({"source_fps": 60})
        assert self._svc("").compute_score(stream) == 0
        # no operator
        assert self._svc("source_fps").compute_score(stream) == 0
        assert self._svc("source_fps|>=|notanumber").compute_score(stream) == 0


class TestEvaluateRules:
    """evaluate_rules reports every matching rule with its point contribution."""

    def test_returns_every_matching_rule(self):
        rules = [
            StreamOrderingRule("regex", r"(?i)1080p", 20),
            StreamOrderingRule("regex", r"(?i)espn", 10),
        ]
        svc = StreamOrderingService(rules)
        evals = svc.evaluate_rules(_stream("ESPN 1080p"))

        assert [(e.type, e.points) for e in evals] == [("regex", 20), ("regex", 10)]

    def test_non_matching_rules_are_omitted(self):
        svc = StreamOrderingService([StreamOrderingRule("regex", r"(?i)espn", 10)])
        assert svc.evaluate_rules(_stream("Fox 1080p")) == []

    def test_no_rules_returns_empty(self):
        assert StreamOrderingService([]).evaluate_rules(_stream("anything")) == []


class TestSortStreams:
    """sort_streams ranks by total score descending, added_at as a tiebreak."""

    def _stream(self, stream_id: int, name: str, added_at: int) -> ManagedChannelStream:
        return ManagedChannelStream(
            id=stream_id, managed_channel_id=1, dispatcharr_stream_id=stream_id,
            stream_name=name, added_at=added_at,
        )

    def test_sorts_by_descending_score(self):
        svc = StreamOrderingService([
            StreamOrderingRule("regex", r"(?i)1080p", 20),
            StreamOrderingRule("regex", r"(?i)espn", 10),
        ])
        low = self._stream(1, "Fox 720p", 1)
        mid = self._stream(2, "Fox 1080p", 2)
        high = self._stream(3, "ESPN 1080p", 3)
        assert svc.sort_streams([low, high, mid]) == [high, mid, low]

    def test_ties_broken_by_added_at(self):
        svc = StreamOrderingService([StreamOrderingRule("regex", r"(?i)espn", 10)])
        earlier = self._stream(1, "ESPN A", 1)
        later = self._stream(2, "ESPN B", 2)
        assert svc.sort_streams([later, earlier]) == [earlier, later]

    def test_no_rules_falls_back_to_stored_priority(self):
        svc = StreamOrderingService([])
        a = self._stream(1, "A", 5)
        a.priority = 2
        b = self._stream(2, "B", 1)
        b.priority = 1
        assert svc.sort_streams([a, b]) == [b, a]
