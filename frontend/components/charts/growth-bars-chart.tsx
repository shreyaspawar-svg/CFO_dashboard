"use client";

import { useMemo } from "react";
import type { EChartsOption } from "echarts";
import { useTheme } from "next-themes";
import { ChartCard } from "@/components/charts/chart-card";
import { chartThemeFor } from "@/lib/chart-theme";
import { computeGrowthSeries, type FinancialPeriodLite } from "@/lib/income-statement";

/** YoY (annual) / QoQ (quarterly) growth bars for revenue, EBITDA and net
 * income (PLAN.md §4.2) -- computed only over comparable periods, reusing
 * the same comparable_from cutoff the backend already applies to its own
 * growth/CAGR figures, so this never shows a spurious spike across a
 * corporate action. */
export function GrowthBarsChart({
  symbol,
  periods,
  comparableFrom,
  periodKind,
}: {
  symbol: string;
  periods: FinancialPeriodLite[];
  comparableFrom: string | null;
  periodKind: "annual" | "quarterly";
}) {
  const { resolvedTheme } = useTheme();
  const theme = chartThemeFor(resolvedTheme);

  const series = useMemo(() => {
    const revenue = computeGrowthSeries(periods, "revenue", comparableFrom);
    const ebitda = computeGrowthSeries(periods, "ebitda", comparableFrom);
    const netIncome = computeGrowthSeries(periods, "net_income", comparableFrom);
    return {
      labels: revenue.map((r) => r.label),
      revenue: revenue.map((r) => r.growthPct),
      ebitda: ebitda.map((r) => r.growthPct),
      netIncome: netIncome.map((r) => r.growthPct),
      // A gap is already the right visual for both "missing" and "not
      // meaningful" (there's no bar to show either way) -- kept only for
      // the CSV export, so a "n.m." reader isn't left thinking it's just
      // absent data.
      netIncomeReason: netIncome.map((r) => r.reason),
    };
  }, [periods, comparableFrom]);

  const option = useMemo<EChartsOption | null>(() => {
    if (periods.length < 2) return null;
    return {
      grid: { left: 56, right: 16, top: 56, bottom: 40 },
      legend: { top: 0, left: "center", data: ["Revenue", "EBITDA", "Net income"] },
      xAxis: { type: "category", data: series.labels, axisLabel: { color: theme.muted } },
      yAxis: {
        type: "value",
        axisLabel: { color: theme.muted, formatter: "{value}%" },
        splitLine: { lineStyle: { color: theme.border } },
      },
      series: [
        { name: "Revenue", type: "bar", data: series.revenue },
        { name: "EBITDA", type: "bar", data: series.ebitda },
        { name: "Net income", type: "bar", data: series.netIncome },
      ],
    };
  }, [series, theme, periods.length]);

  if (!option) {
    return <div className="h-64 animate-pulse rounded-lg border border-border bg-surface" />;
  }

  return (
    <ChartCard
      title={periodKind === "annual" ? "YoY growth" : "QoQ growth"}
      subtitle="Excludes any span crossing a corporate-action cutoff"
      option={option}
      height={260}
      csv={{
        filename: `${symbol}_growth.csv`,
        headers: ["Period", "Revenue growth %", "EBITDA growth %", "Net income growth %", "Net income growth note"],
        rows: series.labels.map((label, i) => [
          label,
          series.revenue[i],
          series.ebitda[i],
          series.netIncome[i],
          series.netIncomeReason[i] === "not_meaningful" ? "n.m. (prior period <= 0)" : "",
        ]),
      }}
    />
  );
}
