import { useState, useEffect } from "react"
import { useQuery } from "@tanstack/react-query"
import { toast } from "sonner"
import { Loader2, Save } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { CollapsibleSection } from "@/components/ui/collapsible-section"
import { Label } from "@/components/ui/label"
import { Input } from "@/components/ui/input"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
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
 * EPG output settings — output path/window. Lifted out of Settings into the EPG
 * home (v2.7.0 IA). The cron generation scheduler stays in Settings (a system
 * job); only the output-shaping config moves here. The epg fields are part of
 * the shared epg blob (full-PUT), so this loads the COMPLETE epg object and
 * saves it whole. Default durations live in their own component (DefaultDurations).
 */
export function EpgOutputSettings() {
  const { data: epgData } = useEPGSettings()
  const updateEPG = useUpdateEPGSettings()

  const [epg, setEPG] = useState<EPGSettings | null>(null)

  useEffect(() => {
    if (epgData) setEPG(epgData)
  }, [epgData])

  const handleSaveOutput = async () => {
    try {
      if (epg) await updateEPG.mutateAsync(epg)
      toast.success("EPG output settings saved")
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to save")
    }
  }

  return (
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
  )
}

/**
 * Default per-sport event durations. Advanced/rarely-touched config, so it's a
 * CollapsibleSection (collapsed by default) and lives at the bottom of the EPG
 * Output page. Uses the standard full-width table styling.
 */
export function DefaultDurations() {
  const { data: durationsData } = useDurationSettings()
  const updateDurations = useUpdateDurationSettings()

  const [durations, setDurations] = useState<DurationSettings | null>(null)

  useEffect(() => {
    if (durationsData) setDurations(durationsData)
  }, [durationsData])

  const { data: sportsData } = useQuery({
    queryKey: ["sports"],
    queryFn: getSports,
    staleTime: 1000 * 60 * 60,
  })
  const sportsMap = sportsData?.sports

  const handleSaveDurations = async () => {
    try {
      if (durations) await updateDurations.mutateAsync(durations)
      toast.success("Default durations saved")
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to save")
    }
  }

  return (
    <CollapsibleSection title="Default Durations" persistKey="epg.default-durations">
      <p className="text-sm text-muted-foreground mb-3">
        Default event durations by sport, in hours.
      </p>
      <div className="border border-border rounded-lg overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Sport</TableHead>
              <TableHead className="text-right">Hours</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {durations &&
              Object.entries(durations)
                .sort((a, b) =>
                  getSportDisplayName(a[0], sportsMap).localeCompare(
                    getSportDisplayName(b[0], sportsMap)
                  )
                )
                .map(([sport, hours]) => (
                  <TableRow key={sport}>
                    <TableCell>{getSportDisplayName(sport, sportsMap)}</TableCell>
                    <TableCell className="text-right">
                      <Input
                        id={`duration-${sport}`}
                        className="w-20 h-8 ml-auto"
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
                    </TableCell>
                  </TableRow>
                ))}
          </TableBody>
        </Table>
      </div>

      <Button
        className="mt-3"
        onClick={handleSaveDurations}
        disabled={updateDurations.isPending}
      >
        {updateDurations.isPending ? (
          <Loader2 className="h-4 w-4 mr-1 animate-spin" />
        ) : (
          <Save className="h-4 w-4 mr-1" />
        )}
        Save
      </Button>
    </CollapsibleSection>
  )
}
