"use client";

import { useMemo } from "react";
import type { EChartsOption } from "echarts";
import { useTheme } from "next-themes";
import { ChartCard, breakMarkerEntry } from "@/components/charts/chart-card";
import { chartThemeFor } from "@/lib/chart-theme";
import { marginPct, type FinancialPeriodLite } from "@/lib/income-statement";

/** Revenue/EBITDA/PAT combo chart (PLAN.md §4.2): bars for the absolute
 * figures, margin% lines on a secondary axis. A pre-corporate-action
 * period (per `comparableFrom`) gets a break marker rather than being
 * silently plotted as if it continued the same trend (Phase 4.0's
 * break-marker convention, reused here for the same reason it's used on
 * the price chart). */
export function IncomeStatementChart({
  symbol,
  periods,
  comparableFrom,
}: {
  symbol: string;
  periods: FinancialPeriodLite[];
  comparableFrom: string | null;
}) {
  const { resolvedTheme } = useTheme();
  const theme = chartThemeFor(resolvedTheme);

  const series = useMemo(() => {
    const labels = periods.map((p) => p.fiscal_year);
    const revenue = periods.map((p) => p.line_items.revenue ?? null);
    const ebitda = periods.map((p) => p.line_items.ebitda ?? null);
    const netIncome = periods.map((p) => p.line_items.net_income ?? null);
    const ebitdaMargin = periods.map((p) => marginPct(p.line_items.ebitda, p.line_items.revenue));
    const patMargin = periods.map((p) => marginPct(p.line_items.net_income, p.line_items.revenue));
    const cutoffIndex = comparableFrom ? periods.findIndex((p) => p.period_end >= comparableFrom) : -1;
    return { labels, revenue, ebitda, netIncome, ebitdaMargin, patMargin, cutoffIndex };
  }, [periods, comparableFrom]);

  const option = useMemo<EChartsOption | null>(() => {
    if (periods.length === 0) return null;
    const breakMarkLine =
      series.cutoffIndex > 0
        ? {
            symbol: "none",
            silent: true,
            lineStyle: { color: theme.muted, type: "dashed" as const },
            label: { show: false },
            data: [breakMarkerEntry(theme, series.labels[series.cutoffIndex], "Not comparable before this period")],
          }
        : undefined;
    return {
      grid: { left: 64, right: 56, top: 64, bottom: 40 },
      legend: { top: 0, left: "center", data: ["Revenue", "EBITDA", "Net income", "EBITDA margin", "PAT margin"] },
      xAxis: { type: "category", data: series.labels, axisLabel: { color: theme.muted } },
      yAxis: [
        {
          type: "value",
          name: "₹ Cr",
          axisLabel: { color: theme.muted, formatter: (v: number) => v.toLocaleString("en-IN") },
          splitLine: { lineStyle: { color: theme.border } },
        },
        {
          type: "value",
          name: "Margin %",
          axisLabel: { color: theme.muted, formatter: "{value}%" },
          splitLine: { show: false },
        },
      ],
      series: [
        { name: "Revenue", type: "bar", data: series.revenue, markLine: breakMarkLine },
        { name: "EBITDA", type: "bar", data: series.ebitda },
        { name: "Net income", type: "bar", data: series.netIncome },
        { name: "EBITDA margin", type: "line", yAxisIndex: 1, data: series.ebitdaMargin, showSymbol: false },
        { name: "PAT margin", type: "line", yAxisIndex: 1, data: series.patMargin, showSymbol: false },
      ],
    };
  }, [series, theme, periods.length]);

  if (!option) {
    return <div className="h-80 animate-pulse rounded-lg border border-border bg-surface" />;
  }

  return (
    <ChartCard
      title="Revenue, EBITDA & net income"
      subtitle="Bars: ₹ Cr (left axis) · Lines: margin % (right axis)"
      option={option}
      height={340}
      csv={{
        filename: `${symbol}_income_statement.csv`,
        headers: ["Period", "Revenue", "EBITDA", "Net income", "EBITDA margin %", "PAT margin %"],
        rows: series.labels.map((label, i) => [
          label,
          series.revenue[i],
          series.ebitda[i],
          series.netIncome[i],
          series.ebitdaMargin[i],
          series.patMargin[i],
        ]),
      }}
    />
  );
}
