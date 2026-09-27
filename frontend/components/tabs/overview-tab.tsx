"use client";

import { useState } from "react";
import { PriceChart } from "@/components/charts/price-chart";
import { PerformanceChart } from "@/components/charts/performance-chart";
import { HealthRadarChart } from "@/components/charts/health-radar-chart";
import { RevenuePatChart } from "@/components/charts/revenue-pat-chart";
import { ReturnsTable } from "@/components/returns-table";
import { KeyStatsRow } from "@/components/key-stats-row";
import { NewsList } from "@/components/news-list";
import { ErrorBoundary } from "@/components/error-boundary";
import type { ChartRangeKey } from "@/lib/chart-ranges";

export function OverviewTab({ symbol, template }: { symbol: string; template: string }) {
  // Lifted here (PLAN.md Phase 5.1 item 2) so the Price chart's range
  // toggle and the "Performance vs NIFTY 50" chart always show the same
  // window, instead of each picking its own fixed range independently.
  const [rangeKey, setRangeKey] = useState<ChartRangeKey>("5Y");

  return (
    <div className="space-y-4">
      <ErrorBoundary region="price chart">
        <PriceChart symbol={symbol} rangeKey={rangeKey} onRangeKeyChange={setRangeKey} />
      </ErrorBoundary>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <ErrorBoundary region="performance chart">
          <PerformanceChart symbol={symbol} rangeKey={rangeKey} />
        </ErrorBoundary>
        <ErrorBoundary region="health radar">
          <HealthRadarChart symbol={symbol} />
        </ErrorBoundary>
      </div>

      <ErrorBoundary region="returns table">
        <ReturnsTable symbol={symbol} />
      </ErrorBoundary>

      <div>
        <h3 className="mb-2 text-sm font-medium">Financial snapshot</h3>
        <ErrorBoundary region="financial snapshot">
          <RevenuePatChart symbol={symbol} template={template} />
        </ErrorBoundary>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <ErrorBoundary region="key stats">
          <KeyStatsRow symbol={symbol} />
        </ErrorBoundary>
        <ErrorBoundary region="news">
          <NewsList symbol={symbol} />
        </ErrorBoundary>
      </div>
    </div>
  );
}
