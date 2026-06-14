import { Link, NavLink, Outlet } from "react-router-dom"
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
  Menu,
  X,
} from "lucide-react"
import type { LucideIcon } from "lucide-react"
import { useEffect, useState } from "react"
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

export function MainLayout() {
  const [theme, setTheme] = useState<"dark" | "light">(() => {
    const saved = localStorage.getItem("theme")
    return (saved as "dark" | "light") || "dark"
  })
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false)

  const healthQuery = useQuery({
    queryKey: ["health"],
    queryFn: fetchHealth,
    staleTime: Infinity, // Version won't change during session
  })

  const version = healthQuery.data?.version || "v2.0.0"

  const { startGeneration, isGenerating } = useGenerationProgress()

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
      <nav className="border-b border-border bg-secondary/75 backdrop-blur-md sticky top-0 z-50">
        <div className="max-w-[1440px] mx-auto px-4">
          <div className="flex items-center justify-between h-14 md:h-12">
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

            {/* Desktop Nav Links — stepwise flow */}
            <div className="hidden md:flex items-center gap-1">
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
                    {item.step != null && (
                      <span className="flex h-4 w-4 items-center justify-center rounded-full bg-muted text-[10px] font-semibold">
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

            {/* Desktop Right side */}
            <div className="hidden md:flex items-center gap-3">
              <NavLink
                to="/settings"
                title="Settings"
                className={({ isActive }) =>
                  `p-2 rounded-md transition-colors ${
                    isActive ? "text-primary bg-primary/10" : "hover:bg-accent"
                  }`
                }
              >
                <Settings className="h-4 w-4" />
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

            {/* Mobile Controls */}
            <div className="md:hidden flex items-center gap-1">
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
              <button
                onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
                className="p-2 rounded-md hover:bg-accent transition-colors"
                title="Toggle menu"
              >
                {isMobileMenuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
              </button>
            </div>
          </div>

          {/* Mobile Menu */}
          {isMobileMenuOpen && (
            <div className="md:hidden py-3 flex flex-col gap-2 animate-slide-down">
              {NAV_ITEMS.map((item) => {
                const Icon = item.icon
                return (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    end={item.to === "/"}
                    onClick={() => setIsMobileMenuOpen(false)}
                    className={({ isActive }) =>
                      `flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                        isActive
                          ? "bg-primary/10 text-primary"
                          : "text-muted-foreground hover:text-foreground hover:bg-accent"
                      }`
                    }
                  >
                    <div className="flex items-center justify-center w-5">
                      <Icon className="h-5 w-5" />
                    </div>
                    {item.label}
                    {item.step != null && (
                      <span className="ml-auto flex h-5 w-5 items-center justify-center rounded-full bg-muted text-[10px] font-semibold">
                        {item.step}
                      </span>
                    )}
                  </NavLink>
                )
              })}

              <button
                onClick={() => startGeneration()}
                disabled={isGenerating}
                className="flex items-center gap-3 px-3 py-2 mt-1 rounded-md bg-primary text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:opacity-60"
              >
                <div className="flex items-center justify-center w-5">
                  <Play className="h-5 w-5" />
                </div>
                {isGenerating ? "Generating…" : "Generate EPG"}
              </button>

              <div className="h-px bg-border my-2" />

              <NavLink
                to="/settings"
                onClick={() => setIsMobileMenuOpen(false)}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                    isActive ? "text-primary bg-primary/10" : "text-muted-foreground hover:text-foreground hover:bg-accent"
                  }`
                }
              >
                <div className="flex items-center justify-center w-5">
                  <Settings className="h-5 w-5" />
                </div>
                Settings
              </NavLink>

              <Link
                to="/settings?tab=advanced"
                onClick={() => setIsMobileMenuOpen(false)}
                className="flex items-center justify-between px-3 py-2 mt-1 rounded-md text-sm font-medium text-muted-foreground hover:bg-accent hover:text-foreground transition-colors"
              >
                <span>Version</span>
                <div className="flex items-center gap-2">
                  <span className="text-xs bg-muted px-2 py-0.5 rounded">{version}</span>
                  {updateAvailable && <span className="flex h-2 w-2 rounded-full bg-amber-500" />}
                </div>
              </Link>
            </div>
          )}
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
