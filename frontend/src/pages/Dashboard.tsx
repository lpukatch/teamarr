import { RunHistoryTable } from "@/components/RunHistoryTable"
import { EpgOutput } from "@/components/EpgOutput"
import { ManagedChannelsTable } from "@/components/ManagedChannelsTable"
import { EventMatcherModal, useEventMatcher } from "@/components/EventMatcherModal"
import { useRecentRuns } from "@/hooks/useEPG"

/**
 * Dashboard — the landing page. A lean health-and-control panel (epic 7rfd):
 * status strip up top, recent runs, then collapsed output/diagnostics, with a
 * de-emphasized all-time footer. Composition detail (per-league/group/channel
 * breakdowns) lives on its home tabs, not here.
 */
export function Dashboard() {
  // EPG generation history (shared hook with the EPG output section)
  const { data: runsData } = useRecentRuns(10, "full_epg")
  const runs = runsData?.runs ?? []

  // Event matcher (manual stream correction, opened from the run history rows)
  const matcher = useEventMatcher()

  return (
    <div className="space-y-2">
      {/* Page Header */}
      <div>
        <h1 className="text-xl font-bold">Dashboard</h1>
      </div>

      {/* Status strip — added in 7rfd.1 */}

      {/* EPG Generation History */}
      {runs.length > 0 && (
        <div>
          <h2 className="text-lg font-semibold mb-3">EPG Generation History</h2>
          <div className="border rounded-lg overflow-hidden">
            <RunHistoryTable runs={runs} onFixStream={matcher.handleOpen} />
          </div>
        </div>
      )}

      {/* EPG output diagnostics: URL, coverage analysis, XML preview */}
      <EpgOutput />

      {/* Managed channels (output) — collapsible active + recently-deleted tables */}
      <ManagedChannelsTable />

      {/* Getting Started slot — first-run experience handled by epic 297x */}

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
