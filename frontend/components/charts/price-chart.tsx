"use client";

import { useMemo } from "react";
import type { EChartsOption } from "echarts";
import { useTheme } from "next-themes";
import { ChartCard, breakMarkerEntry } from "@/components/charts/chart-card";
import { chartThemeFor } from "@/lib/chart-theme";
import { simpleMovingAverage } from "@/lib/technical";
import { useHistory, useEvents, useFinancials } from "@/lib/queries";
import { formatRupees } from "@/lib/format";

export function PriceChart({ symbol }: { symbol: string }) {
  const { data: history, isLoading } = useHistory(symbol, "5y", "1d");
  const { data: events } = useEvents(symbol);
  // `comparable_from`/`comparable_from_label` are sourced from the same
  // backend/data/corporate_actions.json the metrics engine already uses --
  // read from the API (already cached elsewhere in the app via this same
  // hook) rather than a local copy that could drift (PLAN.md "Phase 4.1
  // review" item 3).
  const { data: financials } = useFinancials(symbol, "annual");
  const { resolvedTheme } = useTheme();
  const theme = chartThemeFor(resolvedTheme);

  const series = useMemo(() => {
    if (!history || history.bars.length === 0) return null;
    const dates = history.bars.map((b) => b.date.slice(0, 10));
    const closes: (number | null)[] = history.bars.map((b) => b.close ?? null);
    const sma50 = simpleMovingAverage(closes, 50);
    const sma200 = simpleMovingAverage(closes, 200);
    const dividendDates = new Set((events?.dividends ?? []).map((d) => d.date));
    const dividendMarkers = dates
      .map((date, i) => (dividendDates.has(date) ? { xAxis: i } : null))
      .filter((v): v is { xAxis: number } => v !== null);

    // Break marker for a corporate action (demerger/merger/listing) --
    // Phase 4 §4.0: "why a series jumps, not just that it does".
    const cutoffDate = financials?.comparable_from ?? null;
    const cutoffLabel = financials?.comparable_from_label ?? null;
    const cutoffIndex = cutoffDate ? dates.findIndex((d) => d >= cutoffDate) : -1;

    return { dates, closes, sma50, sma200, dividendMarkers, cutoffLabel, cutoffIndex };
  }, [history, events, financials]);

  const option = useMemo<EChartsOption | null>(() => {
    if (!series) return null;
    return {
      grid: { left: 56, right: 16, top: 16, bottom: 40 },
      xAxis: {
        type: "category",
        data: series.dates,
        boundaryGap: false,
        axisLabel: { color: theme.muted },
      },
      yAxis: {
        type: "value",
        scale: true,
        axisLabel: { color: theme.muted, formatter: (v: number) => formatRupees(v, 0) },
        splitLine: { lineStyle: { color: theme.border } },
      },
      legend: { data: ["Price", "SMA 50", "SMA 200"] },
      series: [
        {
          name: "Price",
          type: "line",
          data: series.closes,
          showSymbol: false,
          lineStyle: { width: 1.5 },
          markLine:
            series.dividendMarkers.length || series.cutoffIndex >= 0
              ? {
                  symbol: "none",
                  silent: true,
                  lineStyle: { color: theme.up, type: "dotted", opacity: 0.5 },
                  label: { show: false },
                  data: [
                    ...series.dividendMarkers,
                    ...(series.cutoffIndex >= 0 && series.cutoffLabel
                      ? [breakMarkerEntry(theme, series.cutoffIndex, series.cutoffLabel)]
                      : []),
                  ],
                }
              : undefined,
        },
        { name: "SMA 50", type: "line", data: series.sma50, showSymbol: false, lineStyle: { width: 1 } },
        {
          name: "SMA 200",
          type: "line",
          data: series.sma200,
          showSymbol: false,
          lineStyle: { width: 1 },
        },
      ],
    };
  }, [series, theme]);

  if (isLoading || !option || !series) {
    return <div className="h-80 animate-pulse rounded-lg border border-border bg-surface" />;
  }

  return (
    <ChartCard
      title="Price"
      subtitle="50/200-day moving averages · dotted lines mark dividend payments"
      option={option}
      height={320}
      csv={{
        filename: `${symbol}_price.csv`,
        headers: ["Date", "Close", "SMA50", "SMA200"],
        rows: series.dates.map((date, i) => [date, series.closes[i], series.sma50[i], series.sma200[i]]),
      }}
    />
  );
}
