---
title: Numbering
parent: Channels
grand_parent: User Guide
nav_order: 3
docs_version: "2.7.0"
---

# Numbering

How channel numbers are assigned and how channels are ordered within the lineup.

## Numbering Mode

| Mode | Description |
|------|-------------|
| **Auto** | Sequential numbering from the channel range start. Order is determined by sport/league priority. |
| **Manual** | Per-league starting channel numbers. Each league gets its own block. |

## Channel Range

Both modes use a global channel range:

| Field | Description |
|-------|-------------|
| **Channel Range Start** | First channel number Teamarr can use. In Manual mode, this is the default start for leagues without a configured start. |
| **Channel Range End** | Last channel number — leave empty for no upper limit |

{: .tip }
Set the range start above your existing Dispatcharr channels (e.g., start at 1000 if you already use 1–500) to avoid number collisions.

## Number Stability (Auto Mode)

Controls whether a channel can be **renumbered while its event is live**. Dispatcharr relies on channel numbers staying put, so a game shouldn't jump numbers just because another event started or ended.

| Mode | Behaviour |
|------|-----------|
| **Compact** | Re-sorts every channel into tidy contiguous order on every run (legacy default). A live channel's number can shift when events start or end. |
| **Gapped (sticky)** | Channels are spaced apart by the **gap size** (e.g. 3 → 101, 104, 107). A new event slots into a free number near where it sorts (filling the gap, or reusing a slot freed by an ended event); existing channels keep their number for the whole event lifecycle. |
| **Strict (no drift)** | Existing channels never move. A new event that would displace others is appended to the end of the range instead. Gaps left by ended events are reclaimed only at the daily reset. |

In both **Gapped** and **Strict** modes, a channel's number is fixed for the life of its event. The only time existing numbers change is the **daily re-layout**.

### Daily Re-Layout

To stop gaps accumulating and to restore priority order, a full re-grid runs once per day. It is gated into your generation schedule: the **first generation at or after the configured reset time** re-grids every channel, then it won't run again until the next day.

| Field | Description |
|-------|-------------|
| **Gap Size** | (Gapped mode) spacing between channels at reset. Larger gaps leave more room for late events to slot in without moving anyone. |
| **Daily re-layout** | Toggle the periodic re-grid on/off. With it off, numbers stay sticky indefinitely and gaps are never reclaimed automatically. |
| **Reset Time** | Local time of the low-traffic window for the re-layout (default `04:00`). |

{: .note }
Reset Time is the **server's** local time. In Docker this is usually UTC unless you set the container `TZ` — pick the value accordingly.

{: .note }
Number Stability applies to **Auto** mode. Manual mode uses its own per-league sequential numbering.

## Per-League Starting Channels (Manual Mode)

When Manual mode is selected, a table lists all leagues with a configurable starting channel number for each. Use the search field and the **Subscribed only** toggle to filter the list.

Each league gets sequential numbers starting from its configured start. This lets you group sports into predictable channel ranges (e.g., NFL at 500, NBA at 600, NHL at 700). Leagues without a configured start fall back to the channel range start.

## Channel Ordering

Channel ordering controls *where channels land in the lineup* — distinct from [Stream Priority](stream-priority), which orders streams *inside* a channel.

**Priority Teams** — add teams here and their channels float to the very top of the channel list, ahead of all sport/league/time ordering. A team floats up wherever it plays (league and cup), matched by name within its sport. This is purely an ordering preference — it has no connection to the [Teams](../epg/teams) page or EPG generation.

The **Sort Priority Order** list lets you drag and drop sports and leagues into your preferred order. Higher items get lower channel numbers. Click **Auto-populate** to pre-fill with all currently subscribed sports and leagues.

The full order is: **Priority Teams → Sport → League → Event time**.

{: .note }
Channel numbers are updated on the next EPG generation run.
