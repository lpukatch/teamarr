import { GlobalDefaults } from "@/components/GlobalDefaults"
import { StepTabs } from "@/components/StepTabs"

/**
 * Step 2 — Subscriptions. The sports and leagues you follow (Global Defaults)
 * are the main, expanded content. Team-based EPG ("Team EPG") is NOT here — it
 * is a secondary path that lives buried in the EPG tab.
 */
export function Subscriptions() {
  return (
    <div className="space-y-3">
      <div>
        <h1 className="text-xl font-bold">Subscriptions</h1>
        <p className="text-sm text-muted-foreground">
          The sports and leagues you follow
        </p>
      </div>

      <StepTabs
        tabs={[
          { to: "/subscriptions", label: "Leagues", end: true },
          { to: "/subscriptions/leagues", label: "Custom Leagues" },
        ]}
      />

      <GlobalDefaults />
    </div>
  )
}
