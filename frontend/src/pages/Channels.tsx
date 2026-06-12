import { ExceptionKeywordsCard } from "@/components/ExceptionKeywordsCard"
import { FeedSeparationCard } from "@/components/FeedSeparationCard"

/**
 * Step 5 — Channels. Configuration for how channels are named, sorted, numbered,
 * consolidated, and output to Dispatcharr. The resulting managed-channels table
 * (an output/results view) lives on the Dashboard, not here.
 */
export function Channels() {
  return (
    <div className="space-y-3">
      <div>
        <h1 className="text-xl font-bold">Channels</h1>
        <p className="text-sm text-muted-foreground">
          How channels are named, sorted, numbered, and output to Dispatcharr
        </p>
      </div>

      <ExceptionKeywordsCard />
      <FeedSeparationCard />
    </div>
  )
}
