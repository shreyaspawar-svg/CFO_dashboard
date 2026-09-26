"use client";

import { useState } from "react";
import { useFinancials } from "@/lib/queries";
import { IncomeStatementChart } from "@/components/charts/income-statement-chart";
import { GrowthBarsChart } from "@/components/charts/growth-bars-chart";
import { WaterfallChart } from "@/components/charts/waterfall-chart";
import { IncomeStatementTable } from "@/components/income-statement-table";
import { ErrorBoundary } from "@/components/error-boundary";
import { cn } from "@/lib/utils";
import type { Template } from "@/lib/kpi-templates";
import type { FinancialPeriodLite } from "@/lib/income-statement";

export function IncomeStatementTab({ symbol, template }: { symbol: string; template: string }) {
  const [periodKind, setPeriodKind] = useState<"annual" | "quarterly">("annual");
  const { data: financials, isLoading } = useFinancials(symbol, periodKind);

  const periods: FinancialPeriodLite[] = financials?.income_statement ?? [];
  const comparableFrom = financials?.comparable_from ?? null;
  const latestPeriod = periods.length > 0 ? periods[periods.length - 1] : null;

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-1" role="tablist" aria-label="Statement period">
        {(["annual", "quarterly"] as const).map((kind) => (
          <button
            key={kind}
            role="tab"
            aria-selected={periodKind === kind}
            onClick={() => setPeriodKind(kind)}
            className={cn(
              "rounded-md border px-3 py-1 text-xs capitalize transition-colors",
              periodKind === kind
                ? "border-accent bg-accent/10 text-accent"
                : "border-border text-muted hover:text-foreground"
            )}
          >
            {kind}
          </button>
        ))}
      </div>

      {isLoading || !financials ? (
        <div className="h-80 animate-pulse rounded-lg border border-border bg-surface" />
      ) : (
        <>
          <ErrorBoundary region="income statement chart">
            <IncomeStatementChart symbol={symbol} periods={periods} comparableFrom={comparableFrom} />
          </ErrorBoundary>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <ErrorBoundary region="growth bars">
              <GrowthBarsChart
                symbol={symbol}
                periods={periods}
                comparableFrom={comparableFrom}
                periodKind={periodKind}
              />
            </ErrorBoundary>
            <ErrorBoundary region="waterfall">
              <WaterfallChart symbol={symbol} latestPeriod={latestPeriod} template={template as Template} />
            </ErrorBoundary>
          </div>

          <ErrorBoundary region="income statement table">
            <IncomeStatementTable periods={periods} comparableFrom={comparableFrom} />
          </ErrorBoundary>
        </>
      )}
    </div>
  );
}
