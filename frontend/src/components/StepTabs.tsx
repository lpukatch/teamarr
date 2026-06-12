import { NavLink } from "react-router-dom"

export interface StepTab {
  to: string
  label: string
  end?: boolean
}

/**
 * Lightweight secondary nav for IA steps that aggregate more than one page
 * (e.g. Subscriptions = Teams + Custom Leagues; EPG = output + Templates).
 * Keeps every sub-page reachable from its step home while the v2.7.0 overhaul
 * progressively merges their content.
 */
export function StepTabs({ tabs }: { tabs: StepTab[] }) {
  return (
    <div className="flex items-center gap-1 border-b border-border pb-1">
      {tabs.map((tab) => (
        <NavLink
          key={tab.to}
          to={tab.to}
          end={tab.end}
          className={({ isActive }) =>
            `px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
              isActive
                ? "bg-primary/10 text-primary"
                : "text-muted-foreground hover:text-foreground hover:bg-accent"
            }`
          }
        >
          {tab.label}
        </NavLink>
      ))}
    </div>
  )
}
