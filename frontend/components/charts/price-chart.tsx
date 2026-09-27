"use client";

import { useMemo } from "react";
import type { EChartsOption } from "echarts";
import { useTheme } from "next-themes";
import { ChartCard, breakMarkerEntry } from "@/components/charts/chart-card";
import { chartThemeFor } from "@/lib/chart-theme";
import { simpleMovingAverage, thinnedTickInterval } from "@/lib/technical";
import { useHistory, useEvents, useFinancials } from "@/lib/queries";
import { formatRupees } from "@/lib/format";
import { cn } from "@/lib/utils";
import { CHART_RANGE_OPTIONS, type ChartRangeKey } from "@/lib/chart-ranges";

export function PriceChart({
  symbol,
  rangeKey,
  onRangeKeyChange,
}: {
  symbol: string;
  rangeKey: ChartRangeKey;
  onRangeKeyChange: (key: ChartRangeKey) => void;
}) {
  const { range, interval, livePoll } = CHART_RANGE_OPTIONS[rangeKey];
  // Same `<ReactECharts>` instance stays mounted across polls (PLAN.md
  // Phase 5 §B.3): each new 1D tick just hands the chart a refreshed
  // `data` array through the existing `option` prop -- echarts-for-react
  // calls `chart.setOption()` on that, it never tears down/remounts the
  // chart, so intraday updates land without a full page or component reload.
  const { data: history, isLoading } = useHistory(symbol, range, interval, { livePoll });
  const { data: events } = useEvents(symbol);
  // `comparable_from`/`comparable_from_label` are sourced from the same
  // backend/data/corporate_actions.json the metrics engine already uses --
  // read from the API (already cached elsewhere in the app via this same
  // hook) rather than a local copy that could drift (PLAN.md "Phase 4.1
  // review" item 3).
  const { data: financials } = useFinancials(symbol, "annual");
  const { resolvedTheme } = useTheme();
  const theme = chartThemeFor(resolvedTheme);

  const isIntraday = rangeKey === "1D";

  const series = useMemo(() => {
    if (!history || history.bars.length === 0) return null;
    // Intraday bars all share one calendar date -- keep the full
    // timestamp for the axis instead of truncating to a date, and skip
    // the daily-chart-only overlays (SMA/dividend/corporate-action
    // markers don't mean anything within a single trading day).
    const dates = history.bars.map((b) => (isIntraday ? b.date : b.date.slice(0, 10)));
    const closes: (number | null)[] = history.bars.map((b) => b.close ?? null);
    if (isIntraday) {
      return { dates, closes, sma50: [], sma200: [], dividendMarkers: [], cutoffLabel: null, cutoffIndex: -1 };
    }
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
  }, [history, events, financials, isIntraday]);

  const option = useMemo<EChartsOption | null>(() => {
    if (!series) return null;
    // Fixed ~6-8 evenly spaced tick labels regardless of range (PLAN.md
    // Phase 5.1 item 1) -- ECharts' own `interval: 'auto'` was leaving
    // 5Y's ~1250 daily points overlapping/illegible; this replaces
    // guessed pixel-width spacing with an explicit, testable tick count,
    // without rotating labels into illegibility either.
    const tickInterval = thinnedTickInterval(series.dates.length);
    return {
      grid: { left: 56, right: 16, top: isIntraday ? 16 : 48, bottom: 40 },
      xAxis: {
        type: "category",
        data: series.dates,
        boundaryGap: false,
        axisLabel: { color: theme.muted, show: !isIntraday, interval: tickInterval },
      },
      yAxis: {
        type: "value",
        scale: true,
        axisLabel: { color: theme.muted, formatter: (v: number) => formatRupees(v, 0) },
        splitLine: { lineStyle: { color: theme.border } },
      },
      // Explicit top/left (PLAN.md Phase 5.1 item 1 follow-up): without
      // it, this defaulted to a position that collided with the x-axis
      // date labels at the bottom of the plot -- invisible before the
      // tick-thinning fix only because the un-thinned labels were already
      // an illegible mass there.
      legend: isIntraday ? undefined : { top: 0, left: "center", data: ["Price", "SMA 50", "SMA 200"] },
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
        ...(isIntraday
          ? []
          : [
              { name: "SMA 50", type: "line" as const, data: series.sma50, showSymbol: false, lineStyle: { width: 1 } },
              {
                name: "SMA 200",
                type: "line" as const,
                data: series.sma200,
                showSymbol: false,
                lineStyle: { width: 1 },
              },
            ]),
      ],
    };
  }, [series, theme, isIntraday]);

  if (isLoading || !option || !series) {
    return <div className="h-80 animate-pulse rounded-lg border border-border bg-surface" />;
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-1" role="tablist" aria-label="Price chart range">
        {(Object.keys(CHART_RANGE_OPTIONS) as ChartRangeKey[]).map((key) => (
          <button
            key={key}
            role="tab"
            aria-selected={rangeKey === key}
            onClick={() => onRangeKeyChange(key)}
            className={cn(
              "rounded-md border px-2.5 py-1 text-xs transition-colors",
              rangeKey === key ? "border-accent bg-accent/10 text-accent" : "border-border text-muted hover:text-foreground"
            )}
          >
            {key}
          </button>
        ))}
      </div>
      <ChartCard
        title="Price"
        subtitle={
          isIntraday
            ? "Intraday, updates every 60s while the market is open"
            : "50/200-day moving averages · dotted lines mark dividend payments"
        }
        option={option}
        height={320}
        csv={{
          filename: `${symbol}_price.csv`,
          headers: isIntraday ? ["Time", "Close"] : ["Date", "Close", "SMA50", "SMA200"],
          rows: series.dates.map((date, i) =>
            isIntraday ? [date, series.closes[i]] : [date, series.closes[i], series.sma50[i], series.sma200[i]]
          ),
        }}
      />
    </div>
  );
}
