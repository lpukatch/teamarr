import { useState } from "react"
import { Button } from "@/components/ui/button"
import { RunHistoryTable } from "@/components/RunHistoryTable"
import { EpgOutput } from "@/components/EpgOutput"
import { ManagedChannelsTable } from "@/components/ManagedChannelsTable"
import { EventMatcherModal, useEventMatcher } from "@/components/EventMatcherModal"
import { StatusStrip } from "@/components/StatusStrip"
import { useRecentRuns, useStats } from "@/hooks/useEPG"

const RUNS_PREVIEW = 5

function formatDuration(ms: number | null | undefined): string {
  if (!ms) return "0s"
  const seconds = Math.round(ms / 1000)
  if (seconds < 60) return `${seconds}s`
  const mins = Math.floor(seconds / 60)
  const secs = seconds % 60
  return secs > 0 ? `${mins}m ${secs}s` : `${mins}m`
}

/**
 * Dashboard — the landing page. A lean health-and-control panel (epic 7rfd):
 * status strip up top, recent runs, the managed-channel tables, then collapsed
 * EPG output/diagnostics, with a de-emphasized all-time footer. Composition
 * detail (per-league/group/channel breakdowns) lives on its home tabs, not here.
 */
export function Dashboard() {
  // EPG generation history (shared hook with the EPG output section)
  const { data: runsData } = useRecentRuns(10, "full_epg")
  const runs = runsData?.runs ?? []

  // All-time totals (de-emphasized footer)
  const { data: stats } = useStats()

  // Event matcher (manual stream correction, opened from the run history rows)
  const matcher = useEventMatcher()

  const [showAllRuns, setShowAllRuns] = useState(false)
  const visibleRuns = showAllRuns ? runs : runs.slice(0, RUNS_PREVIEW)

  return (
    <div className="space-y-2">
      {/* Page Header */}
      <div>
        <h1 className="text-xl font-bold">Dashboard</h1>
      </div>

      {/* Status strip — at-a-glance system health */}
      <StatusStrip lastRun={runs[0]} />

      {/* EPG Generation History */}
      {runs.length > 0 && (
        <div>
          <h2 className="text-lg font-semibold mb-3">EPG Generation History</h2>
          <div className="border rounded-lg overflow-hidden">
            <RunHistoryTable runs={visibleRuns} onFixStream={matcher.handleOpen} />
          </div>
          {runs.length > RUNS_PREVIEW && (
            <Button
              variant="link"
              size="sm"
              className="px-0 mt-1"
              onClick={() => setShowAllRuns((v) => !v)}
            >
              {showAllRuns ? "Show fewer" : `Show more (${runs.length - RUNS_PREVIEW} more)`}
            </Button>
          )}
        </div>
      )}

      {/* Collapsible output sections — separated from the history above so the
          accordions read as a distinct group. */}
      <div className="space-y-2 border-t pt-4 mt-4">
        {/* Managed channels (output) — collapsible active + recently-deleted
            tables. Frequently-checked output, so it leads the group. */}
        <ManagedChannelsTable />

        {/* EPG output diagnostics: URL, coverage analysis, XML preview (collapsed) */}
        <EpgOutput />
      </div>

      {/* Getting Started slot — first-run experience handled by epic 297x */}

      {/* All-time totals — de-emphasized styled tile */}
      {stats && (
        <div className="mt-2 rounded-lg border bg-muted/20 px-4 py-2 text-xs text-muted-foreground">
          <span className="font-medium text-foreground/70">All-time</span> · {stats.total_runs ?? 0} runs ·{" "}
          {stats.totals?.programmes_generated ?? 0} programmes · {stats.totals?.streams_matched ?? 0} streams matched ·{" "}
          {stats.totals?.channels_created ?? 0} channels created · {stats.totals?.streams_cached ?? 0} cache hits ·{" "}
          {stats.totals?.channels_deleted ?? 0} deleted · avg {formatDuration(stats.avg_duration_ms)}
        </div>
      )}

      {/* Event Matcher Modal */}
      <EventMatcherModal
        open={matcher.open}
        onOpenChange={matcher.setOpen}
        stream={matcher.stream}
        league={matcher.league}
        onLeagueChange={matcher.setLeague}
        targetDate={matcher.targetDate}
        onTargetDateChange={matcher.setTargetDate}
        teamFilter={matcher.teamFilter}
        onTeamFilterChange={matcher.setTeamFilter}
        events={matcher.events}
        loading={matcher.loading}
        submitting={matcher.submitting}
        selectedEventId={matcher.selectedEventId}
        onSelectEvent={matcher.setSelectedEventId}
        onSearch={matcher.handleSearch}
        onCorrect={matcher.handleCorrect}
        onSkip={matcher.handleSkip}
      />
    </div>
  )
}
