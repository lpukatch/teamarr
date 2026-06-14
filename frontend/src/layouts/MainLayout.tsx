import { Link, NavLink, Outlet, useLocation } from "react-router-dom"
import {
  Moon,
  Sun,
  LayoutDashboard,
  Users,
  Layers,
  ScanSearch,
  CalendarDays,
  Tv,
  Settings,
  Play,
} from "lucide-react"
import type { LucideIcon } from "lucide-react"
import { useCallback, useEffect, useState } from "react"
import { Toaster } from "sonner"
import { useQuery } from "@tanstack/react-query"
import { useUpdateCheckSettings, useCheckForUpdates } from "../hooks/useSettings"
import { useGenerationProgress } from "@/contexts/GenerationContext"

// The stepwise user flow (v2.7.0 IA). Dashboard is the landing/overview;
// steps 1–5 are the ordered configuration flow; Generate is the end bookend.
// Connect (Dispatcharr) and Settings live outside the numbered flow.
const NAV_ITEMS: { to: string; label: string; icon: LucideIcon; step?: number }[] = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard },
  { to: "/sources", label: "Sources", icon: Layers, step: 1 },
  { to: "/subscriptions", label: "Subscriptions", icon: Users, step: 2 },
  { to: "/matching", label: "Matching", icon: ScanSearch, step: 3 },
  { to: "/epg", label: "EPG", icon: CalendarDays, step: 4 },
  { to: "/channels", label: "Channels", icon: Tv, step: 5 },
]

async function fetchHealth(): Promise<{ status: string; version: string }> {
  const resp = await fetch("/health")
  return resp.json()
}

const VISITED_STEPS_KEY = "teamarr.visitedSteps"

/**
 * First-run guidance: the step numbers (0 Settings, 1–5) act as a "do this
 * next" affordance and drop off once a step has been visited. Visited steps
 * persist in localStorage, so after the first run through the flow the numbers
 * are gone and the nav reads as a normal menu.
 */
function useVisitedSteps() {
  const [visited, setVisited] = useState<Set<number>>(() => {
    try {
      const raw = localStorage.getItem(VISITED_STEPS_KEY)
      return new Set<number>(raw ? JSON.parse(raw) : [])
    } catch {
      return new Set<number>()
    }
  })

  const markVisited = useCallback((step: number) => {
    setVisited((prev) => {
      if (prev.has(step)) return prev
      const next = new Set(prev)
      next.add(step)
      try {
        localStorage.setItem(VISITED_STEPS_KEY, JSON.stringify([...next]))
      } catch {
        // ignore storage failures — numbers just won't persist
      }
      return next
    })
  }, [])

  return { visited, markVisited }
}

export function MainLayout() {
  const [theme, setTheme] = useState<"dark" | "light">(() => {
    const saved = localStorage.getItem("theme")
    return (saved as "dark" | "light") || "dark"
  })

  const healthQuery = useQuery({
    queryKey: ["health"],
    queryFn: fetchHealth,
    staleTime: Infinity, // Version won't change during session
  })

  const version = healthQuery.data?.version || "v2.0.0"

  const { startGeneration, isGenerating } = useGenerationProgress()

  // First-run step numbers: mark a step visited once its page is open.
  const location = useLocation()
  const { visited, markVisited } = useVisitedSteps()
  useEffect(() => {
    const path = location.pathname
    if (path.startsWith("/settings")) {
      markVisited(0)
      return
    }
    for (const item of NAV_ITEMS) {
      if (item.step != null && item.to !== "/" && path.startsWith(item.to)) {
        markVisited(item.step)
        break
      }
    }
  }, [location.pathname, markVisited])

  // Update check
  const updateSettingsQuery = useUpdateCheckSettings()
  const updateInfoQuery = useCheckForUpdates(updateSettingsQuery.data?.enabled ?? false)
  const updateAvailable = updateInfoQuery.data?.update_available ?? false

  useEffect(() => {
    document.documentElement.classList.remove("light", "dark")
    document.documentElement.classList.add(theme)
    localStorage.setItem("theme", theme)
  }, [theme])

  const toggleTheme = () => {
    setTheme((t) => (t === "dark" ? "light" : "dark"))
  }

  return (
    <div className="min-h-screen bg-background text-foreground">
      {/* Navbar */}
      <nav className="border-b border-border bg-secondary/50 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-[1440px] mx-auto px-4">
          <div className="flex items-center justify-between h-12">
            {/* Brand */}
            <Link to="/" className="flex items-center gap-2">
              <img
                src="/logo.svg"
                alt="Teamarr"
                className="h-7 w-7"
                onError={(e) => {
                  e.currentTarget.style.display = "none"
                }}
              />
              <div className="flex flex-col">
                <span className="font-semibold leading-tight">
                  Teamarr
                </span>
                <span className="text-[10px] text-muted-foreground leading-tight hidden sm:block">
                  Sports EPG Generator for Dispatcharr
                </span>
              </div>
            </Link>

            {/* Nav Links — stepwise flow */}
            <div className="flex items-center gap-1">
              {NAV_ITEMS.map((item) => {
                const Icon = item.icon
                return (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    end={item.to === "/"}
                    className={({ isActive }) =>
                      `flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                        isActive
                          ? "bg-primary/10 text-primary"
                          : "text-muted-foreground hover:text-foreground hover:bg-accent"
                      }`
                    }
                  >
                    {item.step != null && !visited.has(item.step) && (
                      <span className="flex h-4 w-4 items-center justify-center rounded-full bg-primary/20 text-primary text-[10px] font-semibold">
                        {item.step}
                      </span>
                    )}
                    <Icon className="h-4 w-4" />
                    {item.label}
                  </NavLink>
                )
              })}

              {/* Generate — end-of-flow bookend */}
              <button
                onClick={() => startGeneration()}
                disabled={isGenerating}
                title="Generate EPG"
                className="ml-1 flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:opacity-60"
              >
                <Play className="h-4 w-4" />
                {isGenerating ? "Generating…" : "Generate"}
              </button>
            </div>

            {/* Right side */}
            <div className="flex items-center gap-3">
              {/* Settings = step 0 (Connect / Dispatcharr). Labeled + badged so
                  it reads as the start of the flow, not just a gear. */}
              <NavLink
                to="/settings"
                title="Settings — connect Dispatcharr (step 0)"
                className={({ isActive }) =>
                  `flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                    isActive
                      ? "bg-primary/10 text-primary"
                      : "text-muted-foreground hover:text-foreground hover:bg-accent"
                  }`
                }
              >
                {!visited.has(0) && (
                  <span className="flex h-4 w-4 items-center justify-center rounded-full bg-primary/20 text-primary text-[10px] font-semibold">
                    0
                  </span>
                )}
                <Settings className="h-4 w-4" />
                Settings
              </NavLink>
              <Link
                to="/settings?tab=advanced"
                className="flex items-center gap-1.5 text-xs text-muted-foreground bg-muted px-2 py-0.5 rounded hover:bg-muted/80 transition-colors"
                title={updateAvailable ? "Update available - click to view" : version}
              >
                {version}
                {updateAvailable && (
                  <span className="flex h-2 w-2 rounded-full bg-amber-500" />
                )}
              </Link>
              <button
                onClick={toggleTheme}
                className="p-2 rounded-md hover:bg-accent transition-colors"
                title="Toggle theme"
              >
                {theme === "dark" ? (
                  <Moon className="h-4 w-4" />
                ) : (
                  <Sun className="h-4 w-4" />
                )}
              </button>
            </div>
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <main className="max-w-[1440px] mx-auto px-4 py-4">
        <Outlet />
      </main>

      {/* Footer */}
      <footer className="border-t border-border mt-auto">
        <div className="max-w-[1440px] mx-auto px-4 py-3">
          <div className="flex items-center justify-center gap-2 text-sm text-muted-foreground">
            <img
              src="/logo.svg"
              alt=""
              className="h-4 w-4 opacity-50"
              onError={(e) => {
                e.currentTarget.style.display = "none"
              }}
            />
            <span className="flex items-center gap-1.5">
              Teamarr - Dynamic Sports EPG Generator for Dispatcharr | {version}
              {updateAvailable && (
                <span className="flex h-2 w-2 rounded-full bg-amber-500" title="Update available" />
              )}
              {window.location.port && ` | Port ${window.location.port}`}
            </span>
          </div>
          <div className="mt-1 text-center text-xs italic text-muted-foreground">
            Jesse, Teamarr will never support curling 🥌
          </div>
        </div>
      </footer>

      {/* Toast notifications - themed styling for all toasts */}
      {/* Position bottom-right to avoid overlapping with top-right UI elements like save buttons */}
      <Toaster
        position="bottom-right"
        toastOptions={{
          className: "!bg-background !text-foreground !border !border-border !rounded-lg !shadow-lg !overflow-hidden",
          style: {
            padding: "12px 16px",
            fontSize: "14px",
            width: "450px",
            maxWidth: "450px",
            wordWrap: "break-word",
            overflowWrap: "break-word",
          },
        }}
      />
    </div>
  )
}
