---
title: Stream Priority
parent: Channels
grand_parent: User Guide
nav_order: 4
docs_version: "2.7.0"
---

# Stream Priority

Configure scoring rules for ordering streams within consolidated channels. When multiple streams are merged into a single channel (see [Consolidation](consolidation)), these rules determine which stream is listed first — the "primary" stream.

This is distinct from [channel ordering](numbering#channel-ordering), which controls a channel's position in the lineup.

## How it works

Each rule is worth a number of **points**. A stream's score is the sum of the points of every rule it matches — not just the first one. Streams within a channel are then ranked by total score, highest first. A stream that matches nothing scores 0 and sorts to the end.

Because every matching rule adds to the score, you can weight several factors at once without having to reorder anything — list order in the editor doesn't affect scoring.

## Rule Types

| Type | Description | Example |
|------|-------------|---------|
| **M3U Account** | Award points to streams from a specific M3U account | "Premium IPTV" = 10 points |
| **Event Group** | Award points to streams from a specific event group | "ESPN+ Group" = 10 points |
| **Regex Pattern** | Award points to streams matching a regex | `(?i)1080p` = 10 points |
| **Stream Type** | Match by how the stream was recognized: **event stream**, **team stream**, or **EPG matched stream**. Optionally narrow a team-stream rule to specific teams. *EPG matched stream* covers streams attached via [EPG program-data matching](../matching/program-matching) — i.e. time-shared linear channels (ESPN, FS1) matched to events through Dispatcharr's program guide. | "Team stream" = 5 points |
| **Home/Away Feed** | Match streams that look like a team's own broadcast (its home or away feed), detected from the stream name. Pick one or more teams. **Invert** flips it to match feeds that are *not* your selected teams (useful for deprioritizing other teams' feeds with negative points). | Selected teams = 15 points |
| **Dispatcharr Group** | Match channel-source streams by their Dispatcharr channel group. The dropdown lists the groups you selected under [Use Dispatcharr channels as an EPG source](../matching/program-matching#dispatcharr-channels-as-an-epg-source). Only channel-source streams carry a Dispatcharr group; regular matched streams are unaffected. | "US \| Sports" = 10 points |
| **Stream Stats** | Match streams whose quality meets numeric thresholds — **resolution width/height**, **source FPS**, **output/audio bitrate**, or **sample rate** — using `>`, `<`, `>=`, `<=`, `=`. Combine several conditions (all must pass for the rule to match). Use it to weight HD / high-bitrate streams ahead of lower-quality ones. | `resolution_height >= 1080` = 20 points |

{: .note }
**Stream Stats** values come from Dispatcharr's external stream probe and are cached per stream (refreshed when older than an hour). A freshly added stream has no stats until Dispatcharr has probed it, so a Stream Stats rule won't match it until then — a stream with no value for the metric is treated as not matching.

Points can be negative — use a negative value to deprioritize streams matching a rule instead of promoting them.

### Team filters

Both **Stream Type** (team streams) and **Home/Away Feed** rules let you pick specific teams. Leaving the team selection empty makes the rule a no-op — a Stream Type rule with no teams matches *all* team streams, while a Home/Away Feed rule with no teams matches nothing. Use the **Default** button to load your configured team-filter include list, or **Clear** to start fresh.

### How Home/Away Feed detection works

Teamarr builds a name-matching pattern from your selected teams' names and abbreviations, then looks for feed indicators in the stream name — a matchup (`vs`, `at`, `@`), a side (`home`/`away`), a camera label (`cam 01`/`cam 02`), or a `(Team feed)` marker. A stream like `Cubs vs Pirates (Home)` is recognized as the Pirates' home feed. Generic streams with no feed markers (for example a plain `Pirates vs Cubs` with no side) don't match this rule. Because detection relies on the stream name, results depend on your provider's naming conventions.

## How to make quality outrank a provider preference

A common goal: prefer streams from a specific provider, but let a meaningfully better stream from *any* provider win when your preferred provider's stream is lower quality. With additive scoring this doesn't require any careful rule ordering — just weight both factors and let the points add up:

| Rule | Points |
|------|--------|
| M3U Account = "Provider A" | 10 |
| Stream Stats: `resolution_height >= 1080` | 20 |
| (no rule for Provider B) | 0 |

| Stream | Matching rules | Score |
|--------|----------------|-------|
| Provider A, 1080p | Provider A + Resolution | 30 |
| Provider B, 1080p | Resolution only | 20 |
| Provider A, 720p | Provider A only | 10 |
| Provider B, 720p | (none) | 0 |

Provider B's 1080p stream now outranks Provider A's 720p stream, while Provider A still wins whenever quality is equal. No rule needs to be listed "above" another — every matching rule always contributes its points.

## Export & Import

Use the **Export** and **Import** buttons in the Stream Priority header to back up your rules or move them between instances.

- **Export** downloads your last **saved** rules as a `stream-ordering-rules.json` file. If you have unsaved edits in the editor, Teamarr warns you first — save before exporting if you want those edits included.
- **Import** reads a rules file and **replaces** your entire current rule set. Rules with an invalid type, value, or points value are skipped. Files exported before the points model (with a `priority` field instead of `points`) are converted automatically — points are assigned in descending steps of 10 following the old priority order — but review the converted values afterward, since the conversion is a best-effort approximation of the old first-match-wins ordering.

Rules that reference an M3U account, event group, or Dispatcharr group match by **name**, so they carry over cleanly to another instance as long as the same names exist there. Team-based rules (Stream Type and Home/Away Feed) reference provider team IDs and only apply to teams present on the target instance.
