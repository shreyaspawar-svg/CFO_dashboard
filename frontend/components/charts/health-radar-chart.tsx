"use client";

import { useMemo } from "react";
import type { EChartsOption } from "echarts";
import { useTheme } from "next-themes";
import { ChartCard } from "@/components/charts/chart-card";
import { chartThemeFor } from "@/lib/chart-theme";
import { useRatios } from "@/lib/queries";
import { formatPercent } from "@/lib/format";
import type { AxisResult } from "@/lib/api";

const AXIS_LABELS: Record<string, string> = {
  growth: "Growth",
  profitability: "Profitability",
  leverage: "Leverage",
  liquidity: "Liquidity",
  efficiency: "Efficiency",
  valuation: "Valuation",
};

function explainAxis(axis: string, result: AxisResult): string {
  if (result.score === null || result.components.length === 0) {
    return `${AXIS_LABELS[axis] ?? axis}: not applicable for this business type`;
  }
  const lines = result.components
    .filter((c) => c.percentile !== null)
    .map(
      (c) =>
        `  ${c.metric} (weight ${(c.weight * 100).toFixed(0)}%): ${
          c.value !== null ? c.value.toFixed(2) : "—"
        } → ${c.percentile!.toFixed(0)}th percentile vs peers`
    );
  return [`${AXIS_LABELS[axis] ?? axis}: ${result.score.toFixed(0)}/100`, ...lines].join("\n");
}

export function HealthRadarChart({ symbol }: { symbol: string }) {
  const { data: ratios, isLoading } = useRatios(symbol);
  const { resolvedTheme } = useTheme();
  const theme = chartThemeFor(resolvedTheme);

  const { option } = useMemo(() => {
    if (!ratios) return { option: null, explanations: [] as string[] };

    const axes = Object.keys(ratios.health_radar);
    const indicator = axes.map((axis) => ({ name: AXIS_LABELS[axis] ?? axis, max: 100 }));
    const values = axes.map((axis) => ratios.health_radar[axis].score ?? 0);
    const explanations = axes.map((axis) => explainAxis(axis, ratios.health_radar[axis]));

    const opt: EChartsOption = {
      tooltip: {
        trigger: "item",
        formatter: () => `<pre style="white-space:pre-wrap;font-size:11px;margin:0">${explanations.join("\n\n")}</pre>`,
      },
      radar: {
        indicator,
        splitLine: { lineStyle: { color: theme.border } },
        splitArea: { show: false },
        axisLine: { lineStyle: { color: theme.border } },
        axisName: { color: theme.foreground, fontSize: 11 },
      },
      series: [
        {
          type: "radar",
          data: [{ value: values, name: symbol, areaStyle: { opacity: 0.15 } }],
        },
      ],
    };
    return { option: opt, explanations };
  }, [ratios, symbol, theme]);

  if (isLoading || !option) {
    return <div className="h-72 animate-pulse rounded-lg border border-border bg-surface" />;
  }

  return (
    <div>
      <ChartCard
        title="Financial health radar"
        subtitle="Each axis is a 0-100 percentile vs sector peers -- hover a point for the metrics behind it"
        option={option}
        height={280}
      />
      <div className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 px-1 text-xs text-muted sm:grid-cols-3">
        {Object.entries(ratios!.health_radar).map(([axis, result]) => (
          <div key={axis} className="flex justify-between">
            <span>{AXIS_LABELS[axis] ?? axis}</span>
            <span className="tabular-nums-fixed">
              {result.score !== null ? formatPercent(result.score, 0) : "—"}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
