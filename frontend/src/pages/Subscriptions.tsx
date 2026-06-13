import { useState } from "react"
import { Lock } from "lucide-react"
import { GlobalDefaults } from "@/components/GlobalDefaults"
import { CustomLeaguesManager } from "@/pages/CustomLeagues"
import { useCustomLeagueCapability } from "@/hooks/useCustomLeagues"
import { SubNav, type SubNavItem } from "@/components/ui/sub-nav"

type Tile = "sportleague" | "soccer" | "teams" | "custom"

/**
 * Step 2 — Subscriptions. The sports and leagues you follow. A 4-tile in-page
 * sub-nav (Sport/League · Soccer · Teams · Custom Leagues) switches the content
 * below. GlobalDefaults stays mounted across the first three tiles so shared
 * subscription state is preserved.
 */
export function Subscriptions() {
  const [activeTile, setActiveTile] = useState<Tile>("sportleague")
  const capabilityQuery = useCustomLeagueCapability()
  const capability = capabilityQuery.data
  const premiumEnabled = !!capability?.enabled

  const tiles: SubNavItem[] = [
    { key: "sportleague", label: "Sport/League" },
    { key: "soccer", label: "Soccer" },
    { key: "teams", label: "Teams" },
    {
      key: "custom",
      label: "Custom Leagues",
      disabled: !premiumEnabled,
      icon: !premiumEnabled ? <Lock className="h-3.5 w-3.5" /> : undefined,
      title: !premiumEnabled ? "Requires a TheSportsDB premium key (Settings)" : undefined,
    },
  ]

  return (
    <div className="space-y-3">
      <div>
        <h1 className="text-xl font-bold">Subscriptions</h1>
      </div>

      <SubNav items={tiles} value={activeTile} onChange={(k) => setActiveTile(k as Tile)} />

      {activeTile === "custom" ? (
        <div className="space-y-3">
          <p className="text-sm italic text-muted-foreground">
            NOTE: Custom League support requires a Premium TheSportsDB API key
          </p>
          <CustomLeaguesManager capability={capability} />
        </div>
      ) : (
        <GlobalDefaults activeTile={activeTile} />
      )}
    </div>
  )
}
