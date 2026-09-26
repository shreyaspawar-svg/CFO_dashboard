"use client";

import { useMemo } from "react";
import type { EChartsOption } from "echarts";
import { useTheme } from "next-themes";
import { ChartCard } from "@/components/charts/chart-card";
import { chartThemeFor } from "@/lib/chart-theme";
import { useHistory } from "@/lib/queries";
import { formatPercent } from "@/lib/format";
import { alignByDate } from "@/lib/technical";

/** Rebases a close-price series to 100 at its first non-null point, so two
 * series with very different price levels (e.g. a ₹2,000 stock vs a
 * ~25,000-point index) can be compared on one axis as % change. */
function rebaseTo100(closes: (number | null)[]): (number | null)[] {
  const base = closes.find((c) => c !== null && c !== 0);
  if (base === undefined || base === null) return closes.map(() => null);
  return closes.map((c) => (c === null ? null : (c / base) * 100));
}

export function PerformanceChart({ symbol }: { symbol: string }) {
  const { data: history, isLoading } = useHistory(symbol, "1y", "1d");
  const { resolvedTheme } = useTheme();
  const theme = chartThemeFor(resolvedTheme);

  const indexed = useMemo(() => {
    if (!history || history.bars.length === 0) return null;
    // Symbol bars and benchmark bars are two independently-fetched series
    // that can have different null-close days -- align by date, not array
    // position (PLAN.md "Phase 4.1 review" item 2).
    const aligned = alignByDate(history.bars, history.benchmark_bars ?? []);
    return {
      dates: aligned.dates,
      symbolIndexed: rebaseTo100(aligned.a),
      benchmarkIndexed: rebaseTo100(aligned.b),
    };
  }, [history]);

  const option = useMemo<EChartsOption | null>(() => {
    if (!indexed) return null;
    return {
      grid: { left: 48, right: 16, top: 16, bottom: 40 },
      xAxis: {
        type: "category",
        data: indexed.dates,
        boundaryGap: false,
        axisLabel: { color: theme.muted },
      },
      yAxis: {
        type: "value",
        scale: true,
        axisLabel: { color: theme.muted, formatter: (v: number) => `${(v - 100).toFixed(0)}%` },
        splitLine: { lineStyle: { color: theme.border } },
      },
      legend: { data: [symbol, "NIFTY 50"] },
      series: [
        {
          name: symbol,
          type: "line",
          data: indexed.symbolIndexed,
          showSymbol: false,
          lineStyle: { width: 1.5 },
        },
        {
          name: "NIFTY 50",
          type: "line",
          data: indexed.benchmarkIndexed,
          showSymbol: false,
          lineStyle: { width: 1.5, type: "dashed" },
        },
      ],
    };
  }, [indexed, symbol, theme]);

  if (isLoading || !option || !indexed) {
    return <div className="h-72 animate-pulse rounded-lg border border-border bg-surface" />;
  }

  const latestSymbol = indexed.symbolIndexed.at(-1);
  const latestBenchmark = indexed.benchmarkIndexed.at(-1);
  const relative =
    latestSymbol !== undefined &&
    latestSymbol !== null &&
    latestBenchmark !== undefined &&
    latestBenchmark !== null
      ? latestSymbol - latestBenchmark
      : null;

  return (
    <ChartCard
      title="Performance vs NIFTY 50"
      subtitle={
        relative !== null
          ? `1Y relative: ${relative >= 0 ? "+" : ""}${formatPercent(relative, 1)}`
          : undefined
      }
      option={option}
      height={280}
      csv={{
        filename: `${symbol}_performance.csv`,
        headers: ["Date", symbol, "NIFTY 50"],
        rows: indexed.dates.map((date, i) => [
          date,
          indexed.symbolIndexed[i],
          indexed.benchmarkIndexed[i],
        ]),
      }}
    />
  );
}
