"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";

const TABS = [
  "Overview",
  "Income Statement",
  "Balance Sheet",
  "Cash Flow",
  "Ratios",
  "Valuation",
  "Peers",
  "Shareholding & Events",
] as const;

export function TabsShell() {
  const [active, setActive] = useState<(typeof TABS)[number]>("Overview");

  return (
    <div className="rounded-lg border border-border bg-surface">
      <div
        role="tablist"
        aria-label="Company detail tabs"
        className="flex gap-1 overflow-x-auto border-b border-border px-2"
        onKeyDown={(e) => {
          if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
          const idx = TABS.indexOf(active);
          const next = e.key === "ArrowRight" ? (idx + 1) % TABS.length : (idx - 1 + TABS.length) % TABS.length;
          setActive(TABS[next]);
        }}
      >
        {TABS.map((tab) => (
          <button
            key={tab}
            role="tab"
            aria-selected={active === tab}
            tabIndex={active === tab ? 0 : -1}
            onClick={() => setActive(tab)}
            className={cn(
              "shrink-0 border-b-2 px-3 py-2.5 text-sm transition-colors",
              active === tab
                ? "border-accent text-accent"
                : "border-transparent text-muted hover:text-foreground"
            )}
          >
            {tab}
          </button>
        ))}
      </div>
      <div role="tabpanel" className="p-6 text-sm text-muted">
        <p className="font-medium text-foreground">{active}</p>
        <p className="mt-1">Coming in Phase 4.</p>
      </div>
    </div>
  );
}
