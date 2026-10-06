"use client";

import { MarketStatusPill } from "@/components/market-status-pill";
import { UnitsToggle } from "@/components/units-toggle";
import { ThemeToggle } from "@/components/theme-toggle";

/**
 * This dashboard is scoped to a single company (Reliance Industries) --
 * see hooks/use-selection.ts. The sector/company comboboxes, the global
 * ⌘K search and the 50-symbol ticker tape all assumed a multi-company
 * universe and were removed rather than hidden; see git history (the
 * NIFTY 50-wide version) if a multi-company mode is ever needed again.
 */
export function TopBar() {
  return (
    <div className="sticky top-0 z-40 border-b border-border bg-background/95 backdrop-blur">
      <div className="flex flex-wrap items-center gap-3 px-4 py-3">
        <span className="brand-title mr-2 text-sm font-semibold tracking-tight">CFO Dashboard</span>
        <span className="text-xs text-muted">Reliance Industries Ltd · RELIANCE</span>

        <div className="flex-1" />

        <MarketStatusPill />
        <UnitsToggle />
        <ThemeToggle />
      </div>
    </div>
  );
}
