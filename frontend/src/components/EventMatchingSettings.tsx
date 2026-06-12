import { useState, useEffect } from "react"
import { useQuery } from "@tanstack/react-query"
import { toast } from "sonner"
import { Loader2, Save } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { Input } from "@/components/ui/input"
import { Select } from "@/components/ui/select"
import { Switch } from "@/components/ui/switch"
import { CheckboxListPicker } from "@/components/ui/checkbox-list-picker"
import {
  useEPGSettings,
  useUpdateEPGSettings,
  useDispatcharrStatus,
} from "@/hooks/useSettings"
import type { EPGSettings } from "@/api/settings"

/**
 * Event Matching + EPG Program Matching settings — how streams/static channels
 * are matched to events. Lifted out of Settings into the Matching home (v2.7.0 IA).
 *
 * These fields live in the shared epg blob (full-PUT), so this card holds the
 * COMPLETE epg object and saves it whole — only its own fields changed.
 */
export function EventMatchingSettings() {
  const { data: epgData } = useEPGSettings()
  const updateEPG = useUpdateEPGSettings()
  const dispatcharrStatus = useDispatcharrStatus()

  const [epg, setEPG] = useState<EPGSettings | null>(null)
  useEffect(() => {
    if (epgData) setEPG(epgData)
  }, [epgData])

  const channelGroupsQuery = useQuery({
    queryKey: ["dispatcharr-channel-groups"],
    queryFn: async () => {
      const response = await fetch("/api/v1/dispatcharr/channel-groups?exclude_m3u=false")
      if (!response.ok) return []
      return response.json() as Promise<{ id: number; name: string; from_m3u: boolean }[]>
    },
    enabled: dispatcharrStatus.data?.connected ?? false,
    retry: false,
  })

  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle>Event Matching</CardTitle>
          <CardDescription>
            Configure how streams are matched to sporting events
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="event-lookahead">Event Lookahead</Label>
            <Select
              id="event-lookahead"
              value={String(epg?.event_match_days_ahead ?? 3)}
              onChange={(e) =>
                epg && setEPG({
                  ...epg,
                  event_match_days_ahead: parseInt(e.target.value),
                })
              }
            >
              <option value="1">1 day</option>
              <option value="3">3 days</option>
              <option value="7">7 days</option>
              <option value="14">14 days</option>
              <option value="30">30 days</option>
            </Select>
            <p className="text-xs text-muted-foreground">
              How far ahead to match streams to events
            </p>
          </div>

          <Button
            onClick={async () => {
              try {
                if (epg) await updateEPG.mutateAsync(epg)
                toast.success("Event matching settings saved")
              } catch (err) {
                toast.error(err instanceof Error ? err.message : "Failed to save")
              }
            }}
            disabled={updateEPG.isPending}
          >
            {updateEPG.isPending ? (
              <Loader2 className="h-4 w-4 mr-1 animate-spin" />
            ) : (
              <Save className="h-4 w-4 mr-1" />
            )}
            Save
          </Button>
        </CardContent>
      </Card>

      {/* EPG Program Matching Card (per-group EPG matching tuning) */}
      <Card>
        <CardHeader>
          <CardTitle>EPG Program Matching</CardTitle>
          <CardDescription>
            Match static-named linear channels (ESPN, FS1) to events via Dispatcharr's
            program guide — enabled per event group
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            <div>
              <p className="text-sm text-muted-foreground pt-1">
                Match static-named linear channels (ESPN, NBA1) to events via Dispatcharr's
                program guide, then time-share one stream across multiple event channels.
                Turn this on per event group in each Event Group's settings — there is no
                global switch. Requires a Dispatcharr build with the program-search API; has
                no effect otherwise. The settings below tune EPG matching for every group
                that opts in.
              </p>
            </div>

            <div className="grid grid-cols-2 gap-4 max-w-md">
              <div>
                <Label htmlFor="epg-pre-buffer">Attach before (minutes)</Label>
                <Input
                  id="epg-pre-buffer"
                  type="number"
                  min={0}
                  value={epg?.epg_stream_pre_buffer_minutes ?? 60}
                  onChange={(e) =>
                    epg &&
                    setEPG({
                      ...epg,
                      epg_stream_pre_buffer_minutes: parseInt(e.target.value) || 0,
                    })
                  }
                />
              </div>
              <div>
                <Label htmlFor="epg-post-buffer">Detach after (minutes)</Label>
                <Input
                  id="epg-post-buffer"
                  type="number"
                  min={0}
                  value={epg?.epg_stream_post_buffer_minutes ?? 60}
                  onChange={(e) =>
                    epg &&
                    setEPG({
                      ...epg,
                      epg_stream_post_buffer_minutes: parseInt(e.target.value) || 0,
                    })
                  }
                />
              </div>
            </div>

            <div className="space-y-2 pt-1">
              <div className="flex items-center gap-2">
                <Switch
                  checked={epg?.epg_channel_source_enabled ?? false}
                  onCheckedChange={(checked) =>
                    epg && setEPG({ ...epg, epg_channel_source_enabled: checked })
                  }
                />
                <Label>Use Dispatcharr channels as an EPG source</Label>
              </div>
              <p className="text-sm text-muted-foreground">
                In addition to per-group M3U matching, pull candidate streams from the
                channels you've already curated in Dispatcharr — using each channel's own
                EPG to match its assigned streams to events. Lets you match only the channel
                versions you've mapped, instead of every stream in a provider group.
                Teamarr's own generated channels are excluded.
              </p>
              {epg?.epg_channel_source_enabled && (
                <div className="pt-1 max-w-md">
                  <CheckboxListPicker
                    label="Dispatcharr groups to include"
                    selected={(epg?.epg_channel_source_groups ?? []).map(String)}
                    onChange={(vals) =>
                      epg &&
                      setEPG({
                        ...epg,
                        epg_channel_source_groups: vals.map(Number),
                      })
                    }
                    items={(channelGroupsQuery.data ?? []).map((g) => ({
                      value: String(g.id),
                      label: g.name,
                    }))}
                    searchPlaceholder="Search Dispatcharr groups..."
                  />
                  <p className="text-xs text-muted-foreground pt-1">
                    Only channels in these groups are scanned for EPG matching — fewer
                    groups means faster generation. Leave empty to include all groups.
                    The selected groups also become sort options under Channels → Stream
                    Ordering.
                  </p>
                </div>
              )}
            </div>

            <div className="space-y-2 pt-1">
              <div className="flex items-center gap-2">
                <Switch
                  checked={epg?.epg_xtream_fallback_enabled ?? false}
                  onCheckedChange={(checked) =>
                    epg && setEPG({ ...epg, epg_xtream_fallback_enabled: checked })
                  }
                />
                <Label>Fall back to Xtream (XC) provider EPG</Label>
              </div>
              <p className="text-sm text-muted-foreground">
                EPG matching normally requires a valid stream-to-EPG mapping in Dispatcharr
                (a curated channel link or an imported-guide name match). As a backup, for
                Xtream Codes (XC) providers, Teamarr can independently fetch the provider's
                own EPG and match against it — covering channels Dispatcharr has no guide for
                (e.g. regional sports networks). The provider's guide is cached on disk per XC
                account and only re-downloaded when older than the cache duration below.
              </p>
              {epg?.epg_xtream_fallback_enabled && (
                <div className="max-w-xs pt-1">
                  <Label htmlFor="epg-xtream-cache">Cache for (hours)</Label>
                  <Input
                    id="epg-xtream-cache"
                    type="number"
                    min={1}
                    value={epg?.epg_xtream_cache_hours ?? 24}
                    onChange={(e) =>
                      epg &&
                      setEPG({
                        ...epg,
                        epg_xtream_cache_hours: parseInt(e.target.value) || 1,
                      })
                    }
                  />
                  <p className="text-xs text-muted-foreground pt-1">
                    How long to reuse a downloaded XC guide before fetching it again.
                    Provider guides change slowly; 24h is a good default.
                  </p>
                </div>
              )}
            </div>
          </div>
        </CardContent>
      </Card>
    </>
  )
}
