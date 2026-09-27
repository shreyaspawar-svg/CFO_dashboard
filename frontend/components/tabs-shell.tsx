"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import { OverviewTab } from "@/components/tabs/overview-tab";
import { IncomeStatementTab } from "@/components/tabs/income-statement-tab";
import { RatiosTab } from "@/components/tabs/ratios-tab";
import { BalanceSheetTab } from "@/components/tabs/balance-sheet-tab";
import { CashFlowTab } from "@/components/tabs/cash-flow-tab";
import { ValuationTab } from "@/components/tabs/valuation-tab";
import { PeersTab } from "@/components/tabs/peers-tab";
import { ShareholdingEventsTab } from "@/components/tabs/shareholding-events-tab";

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
        ) : (
          <ShareholdingEventsTab symbol={symbol} template={template} />
        )}
      </div>
    </div>
  );
}
