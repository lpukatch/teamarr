import { useState, useEffect } from "react"
import { useQuery } from "@tanstack/react-query"
import { toast } from "sonner"
import { Loader2, Save } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { Input } from "@/components/ui/input"
import { Switch } from "@/components/ui/switch"
import { getSports } from "@/api/teams"
import { getSportDisplayName } from "@/lib/utils"
import {
  useEPGSettings,
  useUpdateEPGSettings,
  useDurationSettings,
  useUpdateDurationSettings,
} from "@/hooks/useSettings"
import type { EPGSettings, DurationSettings } from "@/api/settings"

/**
 * EPG output settings — output path/window and default per-sport durations.
 * Lifted out of Settings into the EPG home (v2.7.0 IA). The cron generation
 * scheduler stays in Settings (a system job); only the output-shaping config
 * moves here. The epg fields are part of the shared epg blob (full-PUT), so this
 * loads the COMPLETE epg object and saves it whole.
 */
export function EpgOutputSettings() {
  const { data: epgData } = useEPGSettings()
  const updateEPG = useUpdateEPGSettings()
  const { data: durationsData } = useDurationSettings()
  const updateDurations = useUpdateDurationSettings()

  const [epg, setEPG] = useState<EPGSettings | null>(null)
  const [durations, setDurations] = useState<DurationSettings | null>(null)

  useEffect(() => {
    if (epgData) setEPG(epgData)
  }, [epgData])
  useEffect(() => {
    if (durationsData) setDurations(durationsData)
  }, [durationsData])

  const { data: sportsData } = useQuery({
    queryKey: ["sports"],
    queryFn: getSports,
    staleTime: 1000 * 60 * 60,
  })
  const sportsMap = sportsData?.sports

  const handleSaveOutput = async () => {
    try {
      if (epg) await updateEPG.mutateAsync(epg)
      toast.success("EPG output settings saved")
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to save")
    }
  }

  const handleSaveDurations = async () => {
    try {
      if (durations) await updateDurations.mutateAsync(durations)
      toast.success("Default durations saved")
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to save")
    }
  }

  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle>Output Settings</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-3 gap-4">
            <div className="space-y-2">
              <Label htmlFor="epg-output-path">Output Path</Label>
              <Input
                id="epg-output-path"
                value={epg?.epg_output_path ?? "./teamarr.xml"}
                onChange={(e) => epg && setEPG({ ...epg, epg_output_path: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="epg-days-ahead">Output Days Ahead</Label>
              <Input
                id="epg-days-ahead"
                type="number"
                min={1}
                value={epg?.epg_output_days_ahead ?? 14}
                onChange={(e) =>
                  epg && setEPG({ ...epg, epg_output_days_ahead: parseInt(e.target.value) || 14 })
                }
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="epg-lookback">EPG Start (Hours Ago)</Label>
              <Input
                id="epg-lookback"
                type="number"
                min={0}
                value={epg?.epg_lookback_hours ?? 6}
                onChange={(e) =>
                  epg && setEPG({ ...epg, epg_lookback_hours: parseInt(e.target.value) || 6 })
                }
              />
            </div>
          </div>

          <Button onClick={handleSaveOutput} disabled={updateEPG.isPending}>
            {updateEPG.isPending ? (
              <Loader2 className="h-4 w-4 mr-1 animate-spin" />
            ) : (
              <Save className="h-4 w-4 mr-1" />
            )}
            Save
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>Include Final Events</CardTitle>
            <Switch
              checked={epg?.include_final_events ?? false}
              onCheckedChange={(checked) =>
                epg && setEPG({ ...epg, include_final_events: checked })
              }
            />
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          <p className="text-sm text-muted-foreground">
            Keep completed/final events in the EPG instead of dropping them once they've ended.
          </p>
          <Button onClick={handleSaveOutput} disabled={updateEPG.isPending}>
            {updateEPG.isPending ? (
              <Loader2 className="h-4 w-4 mr-1 animate-spin" />
            ) : (
              <Save className="h-4 w-4 mr-1" />
            )}
            Save
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Default Durations</CardTitle>
          <CardDescription>Default event durations by sport (in hours)</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-x-6 gap-y-2">
            {durations &&
              Object.entries(durations)
                .sort((a, b) =>
                  getSportDisplayName(a[0], sportsMap).localeCompare(
                    getSportDisplayName(b[0], sportsMap)
                  )
                )
                .map(([sport, hours]) => (
                  <div key={sport} className="flex items-center justify-between gap-3">
                    <Label htmlFor={`duration-${sport}`} className="text-sm">
                      {getSportDisplayName(sport, sportsMap)}
                    </Label>
                    <div className="flex items-center gap-1.5">
                      <Input
                        id={`duration-${sport}`}
                        className="w-16 h-8"
                        type="number"
                        step="0.5"
                        min={0.5}
                        value={hours}
                        onChange={(e) =>
                          setDurations({
                            ...durations,
                            [sport]: parseFloat(e.target.value) || 3,
                          })
                        }
                      />
                      <span className="text-sm text-muted-foreground">hrs</span>
                    </div>
                  </div>
                ))}
          </div>

          <Button onClick={handleSaveDurations} disabled={updateDurations.isPending}>
            {updateDurations.isPending ? (
              <Loader2 className="h-4 w-4 mr-1 animate-spin" />
            ) : (
              <Save className="h-4 w-4 mr-1" />
            )}
            Save
          </Button>
        </CardContent>
      </Card>
    </>
  )
}
