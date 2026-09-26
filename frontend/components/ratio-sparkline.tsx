"use client";

import { useMemo } from "react";
import ReactECharts from "echarts-for-react";
import type { EChartsOption } from "echarts";
import { useTheme } from "next-themes";
import { chartThemeFor } from "@/lib/chart-theme";
import type { RatioHistoryPoint } from "@/lib/api";

/** Minimal 4-year sparkline for a ratio card (PLAN.md §4.3 item 2) -- no
 * axes, legend or export (this isn't a standalone chart, just an inline
 * trend indicator), but still gets a break marker at `comparableFrom`,
 * same convention as the full-size charts, so a pre-corporate-action value
 * isn't shown as if it continues the same trend. */
export function RatioSparkline({
  points,
  comparableFrom,
}: {
  points: RatioHistoryPoint[];
  comparableFrom?: string | null;
}) {
  const { resolvedTheme } = useTheme();
  const theme = chartThemeFor(resolvedTheme);

  const option = useMemo<EChartsOption | null>(() => {
    if (points.length < 2) return null;
    const values = points.map((p) => p.value ?? null);
    if (values.every((v) => v === null)) return null;
    const cutoffIndex = comparableFrom ? points.findIndex((p) => p.period_end >= comparableFrom) : -1;

    return {
      grid: { left: 2, right: 2, top: 4, bottom: 4 },
      xAxis: { type: "category", data: points.map((p) => p.fiscal_year), show: false },
      yAxis: { type: "value", show: false, scale: true },
      tooltip: {
        trigger: "axis",
        formatter: (params: unknown) => {
          const p = (params as { name: string; value: number | null }[])[0];
          return p.value == null ? `${p.name}: —` : `${p.name}: ${p.value.toFixed(2)}`;
        },
      },
      series: [
        {
          type: "line",
          data: values,
          showSymbol: false,
          lineStyle: { width: 1.5, color: theme.accent },
          areaStyle: { color: theme.accent, opacity: 0.08 },
          markLine:
            cutoffIndex > 0
              ? {
                  symbol: "none",
                  silent: true,
                  lineStyle: { color: theme.muted, type: "dashed" },
                  label: { show: false },
                  data: [{ xAxis: points[cutoffIndex].fiscal_year }],
                }
              : undefined,
        },
      ],
    };
  }, [points, comparableFrom, theme]);

  if (!option) {
    return <div className="h-8 w-20 shrink-0" aria-hidden />;
  }

  return (
    <ReactECharts
      option={{ backgroundColor: "transparent", ...option }}
      style={{ height: 32, width: 80 }}
      opts={{ renderer: "svg" }}
    />
  );
}
