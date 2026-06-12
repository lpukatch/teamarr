import { useState, useEffect, useRef, useMemo } from "react"
import { useQuery } from "@tanstack/react-query"
import { toast } from "sonner"
import { Loader2, Save, Search, Trash2, ChevronDown, ChevronRight, X } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { Input } from "@/components/ui/input"
import { Select } from "@/components/ui/select"
import { Switch } from "@/components/ui/switch"
import { ChannelProfileSelector } from "@/components/ChannelProfileSelector"
import { SortPriorityManager } from "@/components/SortPriorityManager"
import { StreamOrderingManager } from "@/components/StreamOrderingManager"
import { getLeagues, getSports } from "@/api/teams"
import { cn, getSportDisplayName } from "@/lib/utils"
import {
  useSettings,
  useDispatcharrStatus,
  useUpdateLifecycleSettings,
  useChannelNumberingSettings,
  useUpdateChannelNumberingSettings,
  useLeagueConfigs,
  useUpsertLeagueConfig,
  useDeleteLeagueConfig,
} from "@/hooks/useSettings"
import { useSubscription } from "@/hooks/useSubscription"
import type {
  LifecycleSettings,
  ChannelNumberingSettings,
  SubscriptionLeagueConfig,
} from "@/api/settings"

function LeagueConfigRow({
  leagueName,
  sportName,
  config,
  isExpanded,
  hasOverride,
  channelProfiles,
  channelGroups,
  includeM3uGroups,
  dispatcharrConnected,
  onToggleExpand,
  onSave,
  onClear,
}: {
  leagueName: string
  sportName: string
  config: SubscriptionLeagueConfig | null
  isExpanded: boolean
  hasOverride: boolean
  channelProfiles: { id: number; name: string }[]
  channelGroups: { id: number; name: string; from_m3u?: boolean }[]
  includeM3uGroups: boolean
  dispatcharrConnected: boolean
  onToggleExpand: () => void
  onSave: (data: {
    channel_profile_ids?: (number | string)[] | null
    channel_group_id?: number | null
    channel_group_mode?: string | null
  }) => Promise<void>
  onClear: () => Promise<void>
}) {
  const [localProfileIds, setLocalProfileIds] = useState<(number | string)[]>([])
  const [localGroupId, setLocalGroupId] = useState<number | null>(null)
  const [localGroupMode, setLocalGroupMode] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  // Sync local state when config changes or row expands
  useEffect(() => {
    if (isExpanded && config) {
      setLocalProfileIds(
        config.channel_profile_ids !== null && config.channel_profile_ids !== undefined
          ? config.channel_profile_ids
          : []
      )
      setLocalGroupId(config.channel_group_id)
      setLocalGroupMode(config.channel_group_mode)
    } else if (isExpanded && !config) {
      setLocalProfileIds([])
      setLocalGroupId(null)
      setLocalGroupMode(null)
    }
  }, [isExpanded, config])

  const profileSummary = (() => {
    if (!config?.channel_profile_ids) return "Default"
    if (config.channel_profile_ids.length === 0) return "None"
    const names = config.channel_profile_ids.map((id) => {
      if (typeof id === "string") return id
      const p = channelProfiles.find((cp) => cp.id === id)
      return p?.name ?? `#${id}`
    })
    return names.length <= 2 ? names.join(", ") : `${names.length} profiles`
  })()

  const groupSummary = (() => {
    if (!config?.channel_group_id) return "Default"
    const g = channelGroups.find((cg) => cg.id === config.channel_group_id)
    return g?.name ?? `#${config.channel_group_id}`
  })()

  const modeSummary = (() => {
    const mode = config?.channel_group_mode
    if (!mode) return "Default"
    if (mode === "static") return "Static"
    if (mode === "sport") return "Sport"
    if (mode === "league") return "League"
    return `Custom: ${mode}`
  })()

  const handleSave = async () => {
    setSaving(true)
    try {
      await onSave({
        channel_profile_ids: localProfileIds.length > 0 ? localProfileIds : null,
        channel_group_id: localGroupId,
        channel_group_mode: localGroupMode,
      })
    } finally {
      setSaving(false)
    }
  }

  return (
    <>
      <tr
        className={cn(
          "hover:bg-muted/30 cursor-pointer",
          hasOverride && "bg-primary/5",
          isExpanded && "bg-accent"
        )}
        onClick={onToggleExpand}
      >
        <td className="px-3 py-1.5">
          {isExpanded ? (
            <ChevronDown className="h-4 w-4 text-muted-foreground" />
          ) : (
            <ChevronRight className="h-4 w-4 text-muted-foreground" />
          )}
        </td>
        <td className="px-3 py-1.5 text-muted-foreground">{sportName}</td>
        <td className="px-3 py-1.5">{leagueName}</td>
        <td className="px-3 py-1.5">
          <span className={cn("text-xs", !hasOverride && "text-muted-foreground")}>
            {profileSummary}
          </span>
        </td>
        <td className="px-3 py-1.5">
          <span className={cn("text-xs", !hasOverride && "text-muted-foreground")}>
            {groupSummary}
          </span>
        </td>
        <td className="px-3 py-1.5">
          <span className={cn("text-xs", !hasOverride && "text-muted-foreground")}>
            {modeSummary}
          </span>
        </td>
        <td className="px-3 py-1.5 text-right">
          {hasOverride && (
            <Button
              variant="ghost"
              size="sm"
              className="h-6 w-6 p-0"
              onClick={(e) => {
                e.stopPropagation()
                onClear()
              }}
              title="Clear override"
            >
              <X className="h-3 w-3 text-muted-foreground" />
            </Button>
          )}
        </td>
      </tr>
      {isExpanded && (
        <tr>
          <td colSpan={7} className="px-4 py-3 bg-muted/20 border-t-0">
            <div className="space-y-4 max-w-2xl">
              {/* Channel Profiles */}
              <div>
                <Label className="text-sm font-medium">Channel Profiles</Label>
                <p className="text-xs text-muted-foreground mb-2">
                  Override which channel profiles this league's channels are assigned to.
                  Leave empty to inherit global default.
                </p>
                <ChannelProfileSelector
                  selectedIds={localProfileIds}
                  onChange={setLocalProfileIds}
                  disabled={!dispatcharrConnected}
                />
              </div>

              {/* Channel Group */}
              <div>
                <Label className="text-sm font-medium">Channel Group</Label>
                <p className="text-xs text-muted-foreground mb-2">
                  Override which Dispatcharr channel group this league's channels are placed in.
                </p>
                <Select
                  value={localGroupId?.toString() ?? ""}
                  onChange={(e) => {
                    const v = e.target.value
                    setLocalGroupId(v ? parseInt(v) : null)
                  }}
                  disabled={!dispatcharrConnected}
                  className="w-64"
                >
                  <option value="">Default (inherit)</option>
                  {channelGroups
                    .filter(
                      (g) =>
                        includeM3uGroups || !g.from_m3u || g.id === localGroupId,
                    )
                    .map((g) => (
                      <option key={g.id} value={g.id.toString()}>
                        {g.name}
                      </option>
                    ))}
                </Select>
              </div>

              {/* Channel Group Mode */}
              <div>
                <Label className="text-sm font-medium">Channel Group Mode</Label>
                <p className="text-xs text-muted-foreground mb-2">
                  How the channel group is determined: static (use selected group), or dynamic by sport/league name.
                </p>
                <Select
                  value={
                    localGroupMode && !["static", "sport", "league"].includes(localGroupMode)
                      ? "custom"
                      : localGroupMode ?? ""
                  }
                  onChange={(e) => {
                    const v = e.target.value
                    if (v === "custom") {
                      setLocalGroupMode("{sport} | {league}")
                    } else {
                      setLocalGroupMode(v || null)
                    }
                  }}
                  className="w-64"
                >
                  <option value="">Default (inherit)</option>
                  <option value="static">Static (use selected group)</option>
                  <option value="sport">Dynamic by Sport</option>
                  <option value="league">Dynamic by League</option>
                  <option value="custom">Custom pattern</option>
                </Select>
                {localGroupMode && !["static", "sport", "league"].includes(localGroupMode) && (
                  <Input
                    value={localGroupMode}
                    onChange={(e) => setLocalGroupMode(e.target.value)}
                    placeholder="{sport} | {league}"
                    className="w-64 mt-2"
                  />
                )}
              </div>

              {/* Actions */}
              <div className="flex gap-2 pt-1">
                <Button
                  size="sm"
                  onClick={(e) => {
                    e.stopPropagation()
                    handleSave()
                  }}
                  disabled={saving}
                >
                  {saving ? (
                    <Loader2 className="h-4 w-4 mr-1 animate-spin" />
                  ) : (
                    <Save className="h-4 w-4 mr-1" />
                  )}
                  Save
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={(e) => {
                    e.stopPropagation()
                    onToggleExpand()
                  }}
                >
                  Cancel
                </Button>
                {hasOverride && (
                  <Button
                    variant="destructive"
                    size="sm"
                    onClick={(e) => {
                      e.stopPropagation()
                      onClear()
                    }}
                  >
                    <Trash2 className="h-4 w-4 mr-1" />
                    Clear Override
                  </Button>
                )}
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  )
}

/**
 * Channel configuration — lifecycle, numbering & consolidation, per-league
 * overrides, sort priority, and stream ordering. Lifted out of Settings into
 * the Channels home (v2.7.0 IA). Self-contained: re-declares the hooks/queries
 * it needs (React Query dedupes by key) and owns the channels-only local state.
 */
export function ChannelConfigSettings() {
  const { data: settings } = useSettings()
  const updateLifecycle = useUpdateLifecycleSettings()
  const { data: channelNumberingData } = useChannelNumberingSettings()
  const updateChannelNumbering = useUpdateChannelNumberingSettings()
  const { data: leagueConfigsData } = useLeagueConfigs()
  const upsertLeagueConfigMutation = useUpsertLeagueConfig()
  const deleteLeagueConfigMutation = useDeleteLeagueConfig()
  const dispatcharrStatus = useDispatcharrStatus()

  // Subscription for league filtering
  const { data: subscription } = useSubscription()
  const subscribedLeagueSlugs = useMemo(
    () => new Set(subscription?.leagues ?? []),
    [subscription]
  )

  const { data: leaguesData } = useQuery({
    queryKey: ["cache", "leagues"],
    queryFn: () => getLeagues(),
  })
  const { data: sportsData } = useQuery({
    queryKey: ["sports"],
    queryFn: getSports,
    staleTime: 1000 * 60 * 60,
  })
  const sportsMap = sportsData?.sports

  const channelProfilesQuery = useQuery({
    queryKey: ["dispatcharr-channel-profiles"],
    queryFn: async () => {
      const response = await fetch("/api/v1/dispatcharr/channel-profiles")
      if (!response.ok) return []
      return response.json() as Promise<{ id: number; name: string }[]>
    },
    enabled: dispatcharrStatus.data?.connected ?? false,
    retry: false,
  })

  const [includeM3uGroups] = useState(false)
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

  // Channels-only local state
  const [lifecycle, setLifecycle] = useState<LifecycleSettings | null>(null)
  const [channelNumbering, setChannelNumbering] = useState<ChannelNumberingSettings>({
    global_channel_mode: "auto",
    league_channel_starts: {},
    global_consolidation_mode: "consolidate",
  })
  const [channelRangeStart, setChannelRangeStart] = useState("")
  const [channelRangeEnd, setChannelRangeEnd] = useState("")
  const [expandedLeagueConfig, setExpandedLeagueConfig] = useState<string | null>(null)
  const [leagueSearch, setLeagueSearch] = useState("")
  const [showSubscribedOnly, setShowSubscribedOnly] = useState(true)

  // Sync lifecycle from combined settings (once available)
  const lifecycleInitRef = useRef(false)
  useEffect(() => {
    if (settings && !lifecycleInitRef.current) {
      lifecycleInitRef.current = true
      setLifecycle(settings.lifecycle)
    }
  }, [settings])

  // Sync channel numbering from its dedicated endpoint
  useEffect(() => {
    if (channelNumberingData) {
      setChannelNumbering(channelNumberingData)
    }
  }, [channelNumberingData])

  // Sync channel range inputs from lifecycle on initial load only
  const channelRangeInitializedRef = useRef(false)
  useEffect(() => {
    if (lifecycle && !channelRangeInitializedRef.current) {
      channelRangeInitializedRef.current = true
      setChannelRangeStart(lifecycle.channel_range_start?.toString() ?? "101")
      setChannelRangeEnd(lifecycle.channel_range_end?.toString() ?? "")
    }
  }, [lifecycle])

  const filteredLeagues = useMemo(() => {
    const all = leaguesData?.leagues ?? []
    const searchLower = leagueSearch.toLowerCase()
    return all
      .filter((l) => {
        if (showSubscribedOnly && !subscribedLeagueSlugs.has(l.slug)) return false
        if (searchLower && !(l.name ?? "").toLowerCase().includes(searchLower)
            && !(l.sport ?? "").toLowerCase().includes(searchLower)) return false
        return true
      })
      .sort((a, b) => {
        const sportCmp = (a.sport ?? "").localeCompare(b.sport ?? "")
        if (sportCmp !== 0) return sportCmp
        return (a.name ?? "").localeCompare(b.name ?? "")
      })
  }, [leaguesData, leagueSearch, showSubscribedOnly, subscribedLeagueSlugs])

  const handleSaveChannelNumbering = async () => {
    try {
      const promises: Promise<unknown>[] = [
        updateChannelNumbering.mutateAsync(channelNumbering),
      ]
      if (lifecycle) {
        promises.push(updateLifecycle.mutateAsync(lifecycle))
      }
      await Promise.all(promises)
      toast.success("Channel numbering settings saved")
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to save")
    }
  }

  return (
    <div className="space-y-2">
      {/* Channel Lifecycle */}
      <Card>
        <CardHeader>
          <CardTitle>Channel Lifecycle</CardTitle>
          <CardDescription>
            Configure when channels are created and deleted for event groups
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="ch-create-timing">Channel Create Timing</Label>
              <Select
                id="ch-create-timing"
                value={lifecycle?.channel_create_timing ?? "same_day"}
                onChange={(e) =>
                  lifecycle && setLifecycle({ ...lifecycle, channel_create_timing: e.target.value })
                }
              >
                <option value="same_day">Same day</option>
                <option value="before_event">Before event + buffer</option>
              </Select>
              <Label htmlFor="ch-pre-buffer" className={lifecycle?.channel_create_timing !== "before_event" ? "text-muted-foreground" : ""}>
                Pre-Event Buffer (hours)
              </Label>
              <Input
                id="ch-pre-buffer"
                type="number"
                min={0}
                max={336}
                disabled={lifecycle?.channel_create_timing !== "before_event"}
                value={Math.round((lifecycle?.channel_pre_buffer_minutes ?? 60) / 60)}
                onChange={(e) => {
                  const val = parseInt(e.target.value)
                  if (!isNaN(val) && lifecycle) {
                    setLifecycle({ ...lifecycle, channel_pre_buffer_minutes: Math.max(0, Math.min(336, val)) * 60 })
                  }
                }}
              />
              <p className="text-xs text-muted-foreground">
                {lifecycle?.channel_create_timing === "before_event"
                  ? "Hours before event start to create channel"
                  : "\u00A0"}
              </p>
            </div>
            <div className="space-y-2">
              <Label htmlFor="ch-delete-timing">Channel Delete Timing</Label>
              <Select
                id="ch-delete-timing"
                value={lifecycle?.channel_delete_timing ?? "same_day"}
                onChange={(e) =>
                  lifecycle && setLifecycle({ ...lifecycle, channel_delete_timing: e.target.value })
                }
              >
                <option value="same_day">Same day</option>
                <option value="after_event">After event + buffer</option>
              </Select>
              <Label htmlFor="ch-post-buffer">Post-Event Buffer (hours)</Label>
              <Input
                id="ch-post-buffer"
                type="number"
                min={0}
                max={336}
                value={Math.round((lifecycle?.channel_post_buffer_minutes ?? 60) / 60)}
                onChange={(e) => {
                  const val = parseInt(e.target.value)
                  if (!isNaN(val) && lifecycle) {
                    setLifecycle({ ...lifecycle, channel_post_buffer_minutes: Math.max(0, Math.min(336, val)) * 60 })
                  }
                }}
              />
              <p className="text-xs text-muted-foreground">
                {lifecycle?.channel_delete_timing === "after_event"
                  ? "Hours after event ends to delete channel"
                  : "Midnight cross-over events will always use post-event buffer"}
              </p>
            </div>
          </div>

          <Button
            onClick={async () => {
              if (!lifecycle) return
              try {
                await updateLifecycle.mutateAsync(lifecycle)
                toast.success("Channel lifecycle settings saved")
              } catch (err) {
                toast.error(err instanceof Error ? err.message : "Failed to save")
              }
            }}
            disabled={updateLifecycle.isPending}
          >
            {updateLifecycle.isPending ? (
              <Loader2 className="h-4 w-4 mr-1 animate-spin" />
            ) : (
              <Save className="h-4 w-4 mr-1" />
            )}
            Save
          </Button>
        </CardContent>
      </Card>

      {/* Channel Numbering & Consolidation */}
      <Card>
        <CardHeader>
          <CardTitle>Channel Numbering & Consolidation</CardTitle>
          <CardDescription>
            Configure how channel numbers are assigned, ordered, and how duplicate streams are handled
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Numbering Mode Toggle */}
          <div className="space-y-3">
            <Label className="text-sm font-medium">Numbering Mode</Label>
            <div className="grid grid-cols-2 gap-3">
              <label className={`flex flex-col p-3 rounded-lg border-2 cursor-pointer transition-colors ${
                channelNumbering.global_channel_mode === "auto"
                  ? "border-primary bg-muted/30"
                  : "border-border hover:border-muted-foreground/50"
              }`}>
                <div className="flex items-center gap-2 mb-1">
                  <input type="radio" name="channel-mode" value="auto"
                    checked={channelNumbering.global_channel_mode === "auto"}
                    onChange={() => setChannelNumbering({
                      ...channelNumbering, global_channel_mode: "auto",
                    })}
                    className="accent-primary" />
                  <span className="font-medium text-sm">Auto</span>
                </div>
                <p className="text-xs text-muted-foreground leading-tight ml-5">
                  Sequential numbering from channel range start. Ordered by sport/league priority.
                </p>
              </label>
              <label className={`flex flex-col p-3 rounded-lg border-2 cursor-pointer transition-colors ${
                channelNumbering.global_channel_mode === "manual"
                  ? "border-primary bg-muted/30"
                  : "border-border hover:border-muted-foreground/50"
              }`}>
                <div className="flex items-center gap-2 mb-1">
                  <input type="radio" name="channel-mode" value="manual"
                    checked={channelNumbering.global_channel_mode === "manual"}
                    onChange={() => setChannelNumbering({
                      ...channelNumbering, global_channel_mode: "manual",
                    })}
                    className="accent-primary" />
                  <span className="font-medium text-sm">Manual</span>
                </div>
                <p className="text-xs text-muted-foreground leading-tight ml-5">
                  Per-league starting channel numbers. Each league gets its own number range.
                </p>
              </label>
            </div>
          </div>

          {/* Channel Range (both modes) */}
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="ch-range-start-num">Channel Range Start</Label>
              <Input
                id="ch-range-start-num"
                type="number"
                min={1}
                value={channelRangeStart}
                onChange={(e) => setChannelRangeStart(e.target.value)}
                onBlur={(e) => {
                  if (!lifecycle) return
                  const val = parseInt(e.target.value)
                  if (!isNaN(val) && val >= 1) {
                    setChannelRangeStart(val.toString())
                    setLifecycle({ ...lifecycle, channel_range_start: val })
                  } else {
                    setChannelRangeStart(
                      lifecycle.channel_range_start?.toString() ?? "101"
                    )
                  }
                }}
              />
              <p className="text-xs text-muted-foreground">
                {channelNumbering.global_channel_mode === "auto"
                  ? "First channel number for all channels"
                  : "Default start for leagues without a configured start"}
              </p>
            </div>
            <div className="space-y-2">
              <Label htmlFor="ch-range-end-num">Channel Range End</Label>
              <Input
                id="ch-range-end-num"
                type="number"
                min={1}
                value={channelRangeEnd}
                onChange={(e) => setChannelRangeEnd(e.target.value)}
                onBlur={(e) => {
                  if (!lifecycle) return
                  if (e.target.value === "") {
                    setChannelRangeEnd("")
                    setLifecycle({ ...lifecycle, channel_range_end: null })
                  } else {
                    const val = parseInt(e.target.value)
                    if (!isNaN(val) && val >= 1) {
                      setChannelRangeEnd(val.toString())
                      setLifecycle({ ...lifecycle, channel_range_end: val })
                    } else {
                      setChannelRangeEnd(
                        lifecycle.channel_range_end?.toString() ?? ""
                      )
                    }
                  }
                }}
                placeholder="No limit"
              />
              <p className="text-xs text-muted-foreground">
                Last channel number (leave empty for no limit)
              </p>
            </div>
          </div>

          {/* Per-League Start Numbers (Manual mode only) */}
          {channelNumbering.global_channel_mode === "manual" && (
            <div className="space-y-3">
              <Label className="text-sm font-medium">
                Per-League Starting Channels
              </Label>
              <p className="text-xs text-muted-foreground">
                Set starting channel numbers for each league. Leagues without a
                configured start will use the channel range start.
              </p>
              {/* Search + subscribed-only filter */}
              <div className="flex items-center gap-3">
                <div className="relative flex-1">
                  <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                  <Input
                    placeholder="Filter leagues..."
                    value={leagueSearch}
                    onChange={(e) => setLeagueSearch(e.target.value)}
                    className="pl-8 h-8"
                  />
                </div>
                <label className="flex items-center gap-2 cursor-pointer text-sm whitespace-nowrap">
                  <Switch
                    checked={showSubscribedOnly}
                    onCheckedChange={setShowSubscribedOnly}
                  />
                  Subscribed only
                </label>
              </div>
              <div className="border rounded-md max-h-64 overflow-y-auto">
                <table className="w-full text-sm">
                  <thead className="bg-muted sticky top-0">
                    <tr>
                      <th className="px-3 py-2 text-left font-medium">Sport</th>
                      <th className="px-3 py-2 text-left font-medium">League</th>
                      <th className="px-3 py-2 text-right font-medium w-32">
                        Start Ch #
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y">
                    {filteredLeagues.map((league) => (
                        <tr key={league.slug} className="hover:bg-muted/30">
                          <td className="px-3 py-1.5 text-muted-foreground">
                            {getSportDisplayName(league.sport, sportsMap)}
                          </td>
                          <td className="px-3 py-1.5">{league.name}</td>
                          <td className="px-3 py-1.5 text-right">
                            <Input
                              type="number"
                              min={1}
                              className="w-24 ml-auto text-right h-7 text-sm"
                              placeholder="—"
                              value={
                                channelNumbering.league_channel_starts[
                                  league.slug
                                ] ?? ""
                              }
                              onChange={(e) => {
                                const starts = {
                                  ...channelNumbering.league_channel_starts,
                                }
                                if (e.target.value === "") {
                                  delete starts[league.slug]
                                } else {
                                  const v = parseInt(e.target.value)
                                  if (!isNaN(v) && v >= 1) starts[league.slug] = v
                                }
                                setChannelNumbering({
                                  ...channelNumbering,
                                  league_channel_starts: starts,
                                })
                              }}
                            />
                          </td>
                        </tr>
                      ))}
                    {filteredLeagues.length === 0 && (
                      <tr>
                        <td colSpan={3} className="px-3 py-4 text-center text-muted-foreground">
                          {leagueSearch ? "No leagues match your search" : "No subscribed leagues"}
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Consolidation Mode */}
          <div className="space-y-3">
            <Label className="text-sm font-medium">Stream Consolidation</Label>
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

          {/* Sort Priority Manager — always visible */}
          <div className="space-y-3">
            <Label className="text-sm font-medium">Channel Ordering</Label>
            <p className="text-xs text-muted-foreground">
              Channels are ordered by Sport → League → Event Time.
              Drag to reorder sport/league priority.
            </p>
            <SortPriorityManager
              currentSortBy="sport_league_time"
              showWhenSortBy="sport_league_time"
            />
          </div>

          <div className="pt-4 border-t">
            <Button
              onClick={handleSaveChannelNumbering}
              disabled={
                updateChannelNumbering.isPending || updateLifecycle.isPending
              }
            >
              {updateChannelNumbering.isPending || updateLifecycle.isPending ? (
                <Loader2 className="h-4 w-4 mr-1 animate-spin" />
              ) : (
                <Save className="h-4 w-4 mr-1" />
              )}
              Save
            </Button>
            <p className="text-xs text-muted-foreground mt-2">
              Channel numbers will be updated on the next EPG generation.
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Per-League Channel Config */}
      <Card>
        <CardHeader>
          <CardTitle>Per-League Channel Config</CardTitle>
          <CardDescription>
            Override channel profiles, channel group, and group mode per league. Leagues without overrides inherit global defaults.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {/* Search + subscribed-only filter */}
          <div className="flex items-center gap-3">
            <div className="relative flex-1">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Filter leagues..."
                value={leagueSearch}
                onChange={(e) => setLeagueSearch(e.target.value)}
                className="pl-8 h-8"
              />
            </div>
            <label className="flex items-center gap-2 cursor-pointer text-sm whitespace-nowrap">
              <Switch
                checked={showSubscribedOnly}
                onCheckedChange={setShowSubscribedOnly}
              />
              Subscribed only
            </label>
          </div>
          <div className="border rounded-md max-h-96 overflow-y-auto">
            <table className="w-full text-sm">
              <thead className="bg-muted sticky top-0 z-10">
                <tr>
                  <th className="px-3 py-2 text-left font-medium w-8"></th>
                  <th className="px-3 py-2 text-left font-medium">Sport</th>
                  <th className="px-3 py-2 text-left font-medium">League</th>
                  <th className="px-3 py-2 text-left font-medium">Profiles</th>
                  <th className="px-3 py-2 text-left font-medium">Channel Group</th>
                  <th className="px-3 py-2 text-left font-medium">Group Mode</th>
                  <th className="px-3 py-2 text-right font-medium w-16"></th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {filteredLeagues.map((league) => {
                    const config = leagueConfigsData?.configs?.find(
                      (c) => c.league_code === league.slug
                    )
                    const isExpanded = expandedLeagueConfig === league.slug
                    const hasOverride = !!config
                    return (
                      <LeagueConfigRow
                        key={league.slug}
                        leagueName={league.name}
                        sportName={getSportDisplayName(league.sport, sportsMap)}
                        config={config ?? null}
                        isExpanded={isExpanded}
                        hasOverride={hasOverride}
                        channelProfiles={channelProfilesQuery.data ?? []}
                        channelGroups={channelGroupsQuery.data ?? []}
                        includeM3uGroups={includeM3uGroups}
                        dispatcharrConnected={dispatcharrStatus.data?.connected ?? false}
                        onToggleExpand={() =>
                          setExpandedLeagueConfig(isExpanded ? null : league.slug)
                        }
                        onSave={async (data) => {
                          try {
                            await upsertLeagueConfigMutation.mutateAsync({
                              leagueCode: league.slug,
                              data,
                            })
                            toast.success(`Saved config for ${league.name}`)
                            setExpandedLeagueConfig(null)
                          } catch {
                            toast.error(`Failed to save config for ${league.name}`)
                          }
                        }}
                        onClear={async () => {
                          try {
                            await deleteLeagueConfigMutation.mutateAsync(league.slug)
                            toast.success(`Cleared config for ${league.name}`)
                          } catch {
                            toast.error(`Failed to clear config for ${league.name}`)
                          }
                        }}
                      />
                    )
                  })}
                {filteredLeagues.length === 0 && (
                  <tr>
                    <td colSpan={7} className="px-3 py-4 text-center text-muted-foreground">
                      {leagueSearch ? "No leagues match your search" : "No subscribed leagues"}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
          <p className="text-xs text-muted-foreground mt-2">
            Click a league row to expand and configure overrides. Changes apply on the next EPG generation.
          </p>
        </CardContent>
      </Card>

      {/* Stream Ordering */}
      <StreamOrderingManager />
    </div>
  )
}
