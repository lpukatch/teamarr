import { ChannelConfigSettings } from "@/components/ChannelConfigSettings"
import { ExceptionKeywordsCard } from "@/components/ExceptionKeywordsCard"
import { FeedSeparationCard } from "@/components/FeedSeparationCard"
import { DispatcharrOutputSettings } from "@/components/DispatcharrOutputSettings"

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

      <ChannelConfigSettings />
      <ExceptionKeywordsCard />
      <FeedSeparationCard />

      <div className="pt-2">
        <h2 className="text-lg font-semibold">Dispatcharr Output</h2>
        <p className="text-sm text-muted-foreground">
          Default profiles, channel group, and logo cleanup for channels pushed to Dispatcharr.
          Connection settings live in Settings.
        </p>
      </div>
      <DispatcharrOutputSettings />
    </div>
  )
}
