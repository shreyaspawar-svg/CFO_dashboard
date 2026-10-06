"use client";

import { useState } from "react";
import dynamic from "next/dynamic";
import { cn } from "@/lib/utils";
import { OverviewTab } from "@/components/tabs/overview-tab";

// Code-split every tab but the default-active Overview (Lighthouse/PLAN.md
// Phase 5 §C.3): each of these pulls in its own echarts-heavy chart
// components, and bundling all 8 tabs' worth of JS into the initial page
// load pushed LCP past 5s for no benefit, since only one tab is visible at
// a time. `ssr: false` is safe here -- every tab is itself a "use client"
// component with no meaningful non-JS content.
const IncomeStatementTab = dynamic(() =>
  import("@/components/tabs/income-statement-tab").then((m) => m.IncomeStatementTab)
);
const RatiosTab = dynamic(() => import("@/components/tabs/ratios-tab").then((m) => m.RatiosTab));
const BalanceSheetTab = dynamic(() =>
  import("@/components/tabs/balance-sheet-tab").then((m) => m.BalanceSheetTab)
);
const CashFlowTab = dynamic(() => import("@/components/tabs/cash-flow-tab").then((m) => m.CashFlowTab));
const ValuationTab = dynamic(() => import("@/components/tabs/valuation-tab").then((m) => m.ValuationTab));
const PeersTab = dynamic(() => import("@/components/tabs/peers-tab").then((m) => m.PeersTab));
const ShareholdingEventsTab = dynamic(() =>
  import("@/components/tabs/shareholding-events-tab").then((m) => m.ShareholdingEventsTab)
);
const KpiScorecardTab = dynamic(() =>
  import("@/components/tabs/kpi-scorecard-tab").then((m) => m.KpiScorecardTab)
);

const TABS = [
  "Overview",
  "Income Statement",
  "Balance Sheet",
  "Cash Flow",
  "Ratios",
  "Valuation",
  "Peers",
  "Shareholding & Events",
  "KPI Scorecard",
] as const;

export function TabsShell({ symbol, template }: { symbol: string; template: string }) {
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
      <div role="tabpanel" className="p-4">
        {active === "Overview" ? (
          <OverviewTab symbol={symbol} template={template} />
        ) : active === "Income Statement" ? (
          <IncomeStatementTab symbol={symbol} template={template} />
        ) : active === "Ratios" ? (
          <RatiosTab symbol={symbol} template={template} />
        ) : active === "Balance Sheet" ? (
          <BalanceSheetTab symbol={symbol} template={template} />
        ) : active === "Cash Flow" ? (
          <CashFlowTab symbol={symbol} template={template} />
        ) : active === "Valuation" ? (
          <ValuationTab symbol={symbol} template={template} />
        ) : active === "Peers" ? (
          <PeersTab symbol={symbol} template={template} />
        ) : active === "Shareholding & Events" ? (
          <ShareholdingEventsTab symbol={symbol} template={template} />
        ) : (
          <KpiScorecardTab symbol={symbol} template={template} />
        )}
      </div>
    </div>
  );
}
