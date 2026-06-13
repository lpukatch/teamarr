import { useState, useEffect } from "react"
import { toast } from "sonner"
import { Loader2, Save } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { ExceptionKeywordsCard } from "@/components/ExceptionKeywordsCard"
import { FeedSeparationCard } from "@/components/FeedSeparationCard"
import {
  useChannelNumberingSettings,
  useUpdateChannelNumberingSettings,
} from "@/hooks/useSettings"
import type { ChannelNumberingSettings } from "@/api/settings"

/**
 * Channels → Consolidation. How events/streams map to channels: the master
 * Consolidate/Separate default, plus the two carve-out mechanisms that split
 * channels apart — exception keywords and feed (home/away) separation.
 *
 * Stream Consolidation lives in the channel-numbering blob (full-PUT). This
 * page only edits global_consolidation_mode; numbering mode and per-league
 * starts (edited under Numbering) ride along untouched. Only one Channels view
 * mounts at a time, so the full-PUT is safe.
 */
export function ChannelConsolidation() {
  const { data: channelNumberingData } = useChannelNumberingSettings()
  const updateChannelNumbering = useUpdateChannelNumberingSettings()

  const [channelNumbering, setChannelNumbering] = useState<ChannelNumberingSettings>({
    global_channel_mode: "auto",
    league_channel_starts: {},
    global_consolidation_mode: "consolidate",
  })

  useEffect(() => {
    if (channelNumberingData) setChannelNumbering(channelNumberingData)
  }, [channelNumberingData])

  return (
    <div className="space-y-3">
      <Card>
        <CardHeader>
          <CardTitle>Stream Consolidation</CardTitle>
          <CardDescription>
            When an event has multiple streams, merge them into one channel or split them apart
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-3">
            <Label className="text-sm font-medium">Default Mode</Label>
            <div className="grid grid-cols-2 gap-3">
              <label className={`flex flex-col p-3 rounded-lg border-2 cursor-pointer transition-colors ${
                channelNumbering.global_consolidation_mode === "consolidate"
                  ? "border-primary bg-muted/30"
                  : "border-border hover:border-muted-foreground/50"
              }`}>
                <div className="flex items-center gap-2 mb-1">
                  <input type="radio" name="consolidation-mode"
                    value="consolidate"
                    checked={channelNumbering.global_consolidation_mode === "consolidate"}
                    onChange={() => setChannelNumbering({
                      ...channelNumbering,
                      global_consolidation_mode: "consolidate",
                    })}
                    className="accent-primary" />
                  <span className="font-medium text-sm">Consolidate</span>
                </div>
                <p className="text-xs text-muted-foreground leading-tight ml-5">
                  Merge multiple streams for the same event into one channel.
                  Exception keywords can override per-stream.
                </p>
              </label>
              <label className={`flex flex-col p-3 rounded-lg border-2 cursor-pointer transition-colors ${
                channelNumbering.global_consolidation_mode === "separate"
                  ? "border-primary bg-muted/30"
                  : "border-border hover:border-muted-foreground/50"
              }`}>
                <div className="flex items-center gap-2 mb-1">
                  <input type="radio" name="consolidation-mode"
                    value="separate"
                    checked={channelNumbering.global_consolidation_mode === "separate"}
                    onChange={() => setChannelNumbering({
                      ...channelNumbering,
                      global_consolidation_mode: "separate",
                    })}
                    className="accent-primary" />
                  <span className="font-medium text-sm">Separate</span>
                </div>
                <p className="text-xs text-muted-foreground leading-tight ml-5">
                  Each stream gets its own channel. More channels, no merging.
                </p>
              </label>
            </div>
          </div>

          <Button
            onClick={async () => {
              try {
                await updateChannelNumbering.mutateAsync(channelNumbering)
                toast.success("Stream consolidation saved")
              } catch (err) {
                toast.error(err instanceof Error ? err.message : "Failed to save")
              }
            }}
            disabled={updateChannelNumbering.isPending}
          >
            {updateChannelNumbering.isPending ? (
              <Loader2 className="h-4 w-4 mr-1 animate-spin" />
            ) : (
              <Save className="h-4 w-4 mr-1" />
            )}
            Save
          </Button>
        </CardContent>
      </Card>

      <ExceptionKeywordsCard />
      <FeedSeparationCard />
    </div>
  )
}
