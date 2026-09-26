"use client";

import { useMemo } from "react";
import type { EChartsOption } from "echarts";
import { useTheme } from "next-themes";
import { ChartCard } from "@/components/charts/chart-card";
import { chartThemeFor } from "@/lib/chart-theme";
import { computeWaterfallSteps, type FinancialPeriodLite } from "@/lib/income-statement";
import type { Template } from "@/lib/kpi-templates";

/** Template-aware waterfall for the latest comparable period (PLAN.md
 * §4.2). Built from an invisible "base" bar stacked with a visible "delta"
 * bar -- the standard ECharts floating-bar technique -- rather than a
 * dedicated waterfall series type. */
export function WaterfallChart({
  symbol,
  latestPeriod,
  template,
}: {
  symbol: string;
  latestPeriod: FinancialPeriodLite | null;
  template: Template;
}) {
  const { resolvedTheme } = useTheme();
  const theme = chartThemeFor(resolvedTheme);

  const steps = useMemo(
    () => (latestPeriod ? computeWaterfallSteps(latestPeriod, template) : []),
    [latestPeriod, template]
  );

  const option = useMemo<EChartsOption | null>(() => {
    if (steps.length === 0) return null;
    const base = steps.map((s) => (s.isTotal ? 0 : Math.min(s.cumulative - s.delta, s.cumulative)));
    const height = steps.map((s) => (s.isTotal ? s.cumulative : Math.abs(s.delta)));
    const colors = steps.map((s) => {
      if (s.isTotal) return theme.accent;
      return s.delta >= 0 ? theme.up : theme.down;
    });
    return {
      legend: { show: false },
      grid: { left: 64, right: 16, top: 32, bottom: 76 },
      xAxis: {
        type: "category",
        data: steps.map((s) => s.label),
        axisLabel: { color: theme.muted, interval: 0, rotate: 30, fontSize: 10 },
      },
      yAxis: {
        type: "value",
        name: "₹ Cr",
        axisLabel: { color: theme.muted, formatter: (v: number) => v.toLocaleString("en-IN") },
        splitLine: { lineStyle: { color: theme.border } },
      },
      series: [
        { name: "base", type: "bar", stack: "waterfall", data: base, itemStyle: { color: "transparent" } },
        {
          name: "value",
          type: "bar",
          stack: "waterfall",
          data: height.map((h, i) => ({ value: h, itemStyle: { color: colors[i] } })),
        },
      ],
    };
  }, [steps, theme]);

  if (!latestPeriod) {
    return <div className="h-72 animate-pulse rounded-lg border border-border bg-surface" />;
  }
  if (!option) {
    return (
      <div className="flex h-72 items-center justify-center rounded-lg border border-border bg-surface text-sm text-muted">
        Not enough line-item data for a waterfall this period.
      </div>
    );
  }

  return (
    <ChartCard
      title={`${latestPeriod.fiscal_year} waterfall`}
      subtitle="Revenue/NII down to net income, latest comparable period"
      option={option}
      height={320}
      csv={{
        filename: `${symbol}_waterfall_${latestPeriod.fiscal_year}.csv`,
        headers: ["Step", "Delta", "Cumulative"],
        rows: steps.map((s) => [s.label, s.isTotal ? null : s.delta, s.cumulative]),
      }}
    />
  );
}
