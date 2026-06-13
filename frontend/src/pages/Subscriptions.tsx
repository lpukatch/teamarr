import { useState } from "react"
import { Lock } from "lucide-react"
import { GlobalDefaults } from "@/components/GlobalDefaults"
import { CustomLeaguesManager } from "@/pages/CustomLeagues"
import { useCustomLeagueCapability } from "@/hooks/useCustomLeagues"
import { cn } from "@/lib/utils"

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

  const tiles: { id: Tile; label: string; disabled?: boolean }[] = [
    { id: "sportleague", label: "Sport/League" },
    { id: "soccer", label: "Soccer" },
    { id: "teams", label: "Teams" },
    { id: "custom", label: "Custom Leagues", disabled: !premiumEnabled },
  ]

  return (
    <div className="space-y-3">
      <div>
        <h1 className="text-xl font-bold">Subscriptions</h1>
      </div>

      <div className="flex flex-wrap gap-2">
        {tiles.map((tile) => {
          const isActive = activeTile === tile.id
          const isDisabled = !!tile.disabled
          return (
            <button
              key={tile.id}
              type="button"
              disabled={isDisabled}
              title={
                isDisabled
                  ? "Requires a TheSportsDB premium key (Settings)"
                  : undefined
              }
              onClick={() => {
                if (!isDisabled) setActiveTile(tile.id)
              }}
              className={cn(
                "rounded-lg border px-4 py-2 text-sm font-medium transition-colors flex items-center gap-1.5",
                isActive
                  ? "bg-primary/10 text-primary border-primary"
                  : "text-muted-foreground hover:text-foreground hover:bg-accent",
                isDisabled && "opacity-50 cursor-not-allowed"
              )}
            >
              {isDisabled && <Lock className="h-3.5 w-3.5" />}
              {tile.label}
            </button>
          )
        })}
      </div>

      {activeTile === "custom" ? (
        <div className="space-y-3">
          <p className="text-sm text-muted-foreground">Premium TheSportsDB only</p>
          <CustomLeaguesManager capability={capability} />
        </div>
      ) : (
        <GlobalDefaults activeTile={activeTile} />
      )}
    </div>
  )
}
