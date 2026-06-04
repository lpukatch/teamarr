---
title: EPG
parent: Settings
grand_parent: User Guide
nav_order: 4
docs_version: "2.3.0"
---

# EPG Settings

Configure EPG output, scheduling, channel reset, and default game durations.

## Output Settings

### Output Path

Where to write the generated XMLTV file. Default: `./data/teamarr.xml`

### Output Days Ahead

How many days of EPG data to include in the output. Default: 14 days.

### EPG Start (Hours Ago)

Include events that started up to this many hours ago. Useful for catching games still in progress. Default: 6 hours.

### Include Final Events

Toggle whether to include completed/final events in the EPG output.

## Scheduled Generation

Enable automatic EPG generation on a schedule.

### Cron Expression

Standard cron format for scheduling. Common presets are available:

| Preset | Expression | Description |
|--------|------------|-------------|
| Every Hour | `0 * * * *` | Run at the top of every hour |
| Every 2 Hours | `0 */2 * * *` | Run every 2 hours |
| Every 4 Hours | `0 */4 * * *` | Run every 4 hours |
| Every 6 Hours | `0 */6 * * *` | Run every 6 hours |
| Daily at Midnight | `0 0 * * *` | Run once daily at midnight |
| Daily at 6 AM | `0 6 * * *` | Run once daily at 6 AM |

### Run Now

Manually trigger an EPG generation run.

## Scheduled Channel Reset

For users experiencing stale channel logos in Jellyfin. Schedule a periodic purge of all Teamarr channels before your media server's guide refresh. Leave disabled if you're not having issues.

### Enable Scheduled Channel Reset

Toggle whether to enable periodic channel reset.

### Reset Schedule (Cron Expression)

Standard cron format for scheduling the reset. Common presets are available:

| Preset | Expression |
|--------|------------|
| Daily 2:30 AM | `30 2 * * *` |
| Daily 3:30 AM | `30 3 * * *` |
| Daily 4:30 AM | `30 4 * * *` |
| Daily 5:30 AM | `30 5 * * *` |

{: .note }
Set this to run shortly before your media server's scheduled guide refresh. Channels will be recreated on the next EPG generation.

## Default Durations

Set default event durations (in hours) for each sport. These are used when the actual event duration is unknown.

| Sport | Default |
|-------|---------|
| Basketball | 3.0 |
| Football | 3.5 |
| Hockey | 3.0 |
| Baseball | 3.5 |
| Soccer | 2.5 |
| MMA | 5.0 |
| Boxing | 4.0 |
| Tennis | 3.0 |
| Golf | 6.0 |
| Racing | 3.0 |
| Cricket | 4.0 |

## EPG Program-Data Matching

Traditional linear channels (ESPN, NBA1, FS1) carry many different games across a day under a single static stream name, so Teamarr can't match them by name. **EPG program-data matching** uses Dispatcharr's program guide to match these streams to events by the program *title* (e.g. "MLB Baseball" / "Chicago Cubs at St. Louis Cardinals"), then **time-shares** one linear stream across many event channels — attaching it to each event's channel only near game time and detaching it after.

| Setting | Description |
|---------|-------------|
| **Match streams using Dispatcharr EPG data** | Global master switch (default off). Has no effect unless the connected Dispatcharr exposes the program-search API. |
| **Use Dispatcharr channels as an EPG source** | Opt-in additive source (default off). Alongside per-group M3U matching, Teamarr pulls candidate streams from the channels you've already curated in Dispatcharr — using each channel's own linked EPG to match its assigned streams to events. Lets you match only the channel versions you've mapped instead of every stream in a provider group. Runs as a hidden system group ("Dispatcharr Channels"); Teamarr's own generated channels are excluded (they are output, not input). |
| **Fall back to Xtream (XC) provider EPG** | Opt-in backup (default off). EPG matching normally needs a valid stream-to-EPG mapping in Dispatcharr; when on, for Xtream Codes (XC) M3U accounts Teamarr fetches the provider's own EPG and matches the still-unresolved streams against it — covering channels (e.g. regional sports networks) Dispatcharr has no guide for. Downloads the provider guide once per XC account per run (cached). |
| **Attach before (minutes)** | How long before a program's start the stream attaches to the event channel. |
| **Detach after (minutes)** | How long after a program's end the stream detaches. |

Enable it **per Event Group** as well (Event Group settings → *EPG program matching*) — only groups that opt in are scanned. The channel still exists for its normal lifecycle (filler + upcoming guide); only the linear *stream* swaps in and out near game time.

{: .note }
Requires a recent Dispatcharr build with the program-search endpoint (`/api/epg/programs/search/`). Older builds ignore the setting. Attach/detach precision is bounded by how often EPG generation runs.

See the full [EPG Program Matching guide](../epg-matching.md) for how stream→guide resolution works (no manual EPG mapping needed), requirements, the **EPG Matched** badge and stream-ordering rule, and troubleshooting.
