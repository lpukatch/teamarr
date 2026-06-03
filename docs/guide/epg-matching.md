---
title: EPG Program Matching
parent: User Guide
nav_order: 10
docs_version: "2.5.7"
---

# EPG Program Matching
{: .no_toc }

Match static-named linear channels (ESPN, FS1, NBA1) to events using Dispatcharr's program guide, and time-share one stream across many event channels near game time.

<details open markdown="block">
  <summary>Table of contents</summary>
  {: .text-delta }
- TOC
{:toc}
</details>

---

## The problem it solves

Teamarr normally matches a stream to an event by reading the **stream name** — `Cubs vs Cardinals` becomes the Cubs–Cardinals game. That works for event-named streams, but a traditional **linear channel** carries many different games across a day under one unchanging name:

> `Fox Sports 1` airs *Wales vs Ghana* at 1pm, an *MLB* game at 4pm, and *College Baseball* at 8pm — all under the single stream name "Fox Sports 1".

The stream name `Fox Sports 1` tells Teamarr nothing about which game is on, so name matching can't place it. **EPG program matching** solves this by reading the channel's **program guide** instead of its name, and attaching the linear stream to each event's channel only for that game's window.

The result: **one** linear stream serves **many** event channels — swapping in shortly before each game and out shortly after — while each event channel keeps its own stable identity, generated EPG, and filler.

---

## How it works

1. **Read the guide.** For each opted-in group, Teamarr asks Dispatcharr for the EPG **programs** airing on the group's streams (`GET /api/epg/programs/search/`).
2. **Match program titles, not stream names.** Each program's title + subtitle (`MLB Baseball` + `Cubs at Cardinals`) goes through the *same* team-matching pipeline Teamarr uses for stream names, and is matched to a real event.
3. **Time-share the stream.** A linear stream that airs many programs is attached to each matched event's channel only for that program's window (start − *attach before*, end + *detach after*), then detached when the window ends. Studio shows and replays are skipped.

### Where the EPG comes from — you don't map it

The program data comes from **Dispatcharr's own EPG sources** — the XMLTV guides you already configured in Dispatcharr. **You do not tell Teamarr which EPG belongs to which group.** Teamarr links each stream to its guide automatically using a precedence cascade (most authoritative first):

| # | Strategy | When it applies |
|---|----------|-----------------|
| 1 | **Direct tvg_id** | Your M3U stream's `tvg-id` already matches an EPG-source channel id (namespace-aligned setups). |
| 2 | **Channel mapping** | The stream is assigned to a Dispatcharr channel whose EPG is linked (`epg_data_id`). This is a *curated* mapping, so it outranks name matching. |
| 3 | **Name match** | The stream's name matches an EPG channel's name exactly after normalization (stripping `HD`/`FHD`/`(US)` etc.). **Strict:** ambiguous names are skipped, so `ESPN` never resolves to `ESPN2`. |

Strategy 3 means EPG matching works on **raw stream groups** — you do **not** need to pre-build streams into Dispatcharr channels first. Teamarr's own generated EPG source (`_Teamarr`) is always excluded, so streams never match against Teamarr's own output.

---

## Requirements

- **Dispatcharr with the program-search API** — `GET /api/epg/programs/search/`, **confirmed on Dispatcharr `0.24.0`**. Teamarr feature-detects this on connect; on older builds the feature simply stays off (the toggle has no effect), with no errors.
- **A configured EPG source in Dispatcharr** whose guide covers your linear channels.
- A stream resolvable to that guide by one of the three strategies above. Streams that resolve to nothing are left to normal name matching.

{: .note }
EPG matching is **opt-in and off by default** — both globally and per group.

---

## Enabling it

### 1. Global switch — Settings → EPG

Turn on **Match streams using Dispatcharr EPG data** (the master switch). When enabled, two buffer fields appear:

| Setting | Default | Description |
|---------|---------|-------------|
| **Attach before (minutes)** | 60 | How long *before* a program's start the stream attaches to the event channel. |
| **Detach after (minutes)** | 60 | How long *after* a program's end the stream detaches. |

Buffers give viewers lead-in/lead-out time and absorb schedule slippage. They apply in full — the buffers you set drive the whole window. If a large buffer makes two adjacent programs on the same channel overlap, the stream is simply attached to **both** event channels during the overlap; nothing is trimmed. Buffer changes take effect on the next generation run, including for already-attached streams.

### 2. Per-group switch — Event Group settings

On each Event Group, enable **EPG program matching**. Only groups that opt in are scanned. This is the right switch for groups that contain linear channels (e.g. a "US \| Sports" group of ESPN/FS1/SEC Network feeds).

Enabling it on a group automatically **bypasses built-in stream filtering** for that group, because static linear names (`ESPN`, `NBA1`) have no `vs`/`@` separator and would otherwise be dropped before matching.

{: .note }
Both switches are required: the global master switch **and** the per-group switch. The global switch with no opted-in groups does nothing; a per-group switch with the global switch off does nothing.

### Bulk enabling

The per-group toggle is also available in **bulk edit** (select multiple groups → Edit) and at **bulk import** time, so you can flip a whole batch of linear-channel groups at once.

---

## Seeing what matched

### The "EPG Matched" badge

Groups with EPG matching enabled show a violet **EPG Matched** badge in the Event Groups list, alongside the existing **Team Streams** / **Regex** badges.

### Preview

Use **Preview stream matches** on a group to see EPG matches before a real generation run — the preview exercises the same EPG path (it carries the stream `tvg_id` through to the matcher).

### Stream ordering — the "EPG Matched" rule

In **Settings → Channels → Stream Ordering**, the **EPG Matched** rule type prioritizes streams that were attached via EPG matching (no value needed). Use it to push time-shared linear streams ahead of — or behind — name-matched streams within a consolidated channel. See [Channels settings](settings/channels.md#stream-ordering).

{: .note }
The ordering rule reads a `match_method` tag stored on each attached stream. Streams attached *before* this feature existed carry no tag until they're re-matched on the next generation run, so the rule applies going forward.

---

## Caveats & limits

- **Attach/detach precision is bounded by generation cadence.** A stream can only swap in/out when EPG generation runs (your scheduled cron). With hourly runs, expect roughly hourly granularity — the buffers exist partly to cover this.
- **Replays and studio shows are intentionally skipped.** Programs tagged *Classic Sport Event* (replays) or *Sports non-event* (studio/talk) don't match. A live channel showing offseason replays will legitimately match little or nothing.
- **A matched event must actually exist.** EPG matching pairs a program to a real event in your subscribed leagues. A guide entry for a game in a league you don't follow (or a finished game) won't match.
- **Strict name matching skips ambiguous names** to avoid wrong matches. Some channels may not resolve by name alone and will rely on the channel-mapping or direct-tvg_id strategies.

---

## Troubleshooting: "nothing matched"

Work down this list:

1. **Both switches on?** Global (Settings → EPG) *and* per-group.
2. **Program-search supported?** It needs a Dispatcharr build with `/api/epg/programs/search/` (0.24.0+). On older builds the feature is silently off.
3. **Do the streams resolve to a guide?** They must match by direct tvg_id, a linked Dispatcharr channel, or an exact normalized name. Channels with no EPG source coverage can't match.
4. **Is anything actually on?** Check the channel's guide — overnight/offseason slots are mostly replays and studio shows, which are skipped by design.
5. **Are the leagues subscribed?** The program's game must map to an event in a league you follow.

---

## Related

- [EPG Settings](settings/epg.md) — the global switch and buffers
- [Channels settings → Stream Ordering](settings/channels.md#stream-ordering) — the EPG Matched ordering rule
- [Consumer layer architecture](../reference/architecture/consumer-layer.md#epg-title-matching-matchingepg_matcherpy-matchingepg_indexpy) — internals
- [Dispatcharr layer architecture](../reference/architecture/dispatcharr-layer.md#program-data-search-epg-matching) — the program-search client
