"use client";

import { PriceChart } from "@/components/charts/price-chart";
import { PerformanceChart } from "@/components/charts/performance-chart";
import { HealthRadarChart } from "@/components/charts/health-radar-chart";
import { ReturnsTable } from "@/components/returns-table";
import { KpiRow } from "@/components/kpi-row";
import { KeyStatsRow } from "@/components/key-stats-row";
import { NewsList } from "@/components/news-list";
import { ErrorBoundary } from "@/components/error-boundary";

export function OverviewTab({ symbol, template }: { symbol: string; template: string }) {
  return (
    <div className="space-y-4">
      <ErrorBoundary region="price chart">
        <PriceChart symbol={symbol} />
      </ErrorBoundary>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <ErrorBoundary region="performance chart">
          <PerformanceChart symbol={symbol} />
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
          <KpiRow symbol={symbol} template={template} />
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
