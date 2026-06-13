import { useState, useEffect } from "react"

/**
 * useState<boolean> for a collapsed/expanded section, persisted to localStorage
 * so a section the user opens stays open across visits. Keyed under a stable
 * namespace; falls back to in-memory state if localStorage is unavailable.
 */
export function usePersistentCollapse(key: string, defaultCollapsed = true) {
  const storageKey = `teamarr.collapse.${key}`

  const [collapsed, setCollapsed] = useState<boolean>(() => {
    try {
      const v = localStorage.getItem(storageKey)
      return v === null ? defaultCollapsed : v === "1"
    } catch {
      return defaultCollapsed
    }
  })

  useEffect(() => {
    try {
      localStorage.setItem(storageKey, collapsed ? "1" : "0")
    } catch {
      /* ignore — non-persistent fallback */
    }
  }, [storageKey, collapsed])

  return [collapsed, setCollapsed] as const
}
