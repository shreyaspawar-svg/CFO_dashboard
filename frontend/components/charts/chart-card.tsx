"use client";

import { useRef } from "react";
import ReactECharts from "echarts-for-react";
import type { EChartsOption } from "echarts";
import { useTheme } from "next-themes";
import { Download } from "lucide-react";
import { Button } from "@/components/ui/button";
import { downloadCsv, downloadPng } from "@/lib/chart-export";
import { chartThemeFor } from "@/lib/chart-theme";

export interface ChartCsvSpec {
  filename: string;
  headers: string[];
  rows: (string | number | null)[][];
}

/**
 * Shared chart shell (Phase 4 §4.0 chart foundation): every chart gets
 * PNG/CSV export, the same dark/light colour theme, and a title/subtitle
 * row, for free. `option` should already encode the two chart-specific
 * conventions this foundation exists to enforce:
 *   - gaps for missing data, never a zero (use `null` in series data --
 *     ECharts' default `connectNulls: false` then shows a visible break).
 *   - break markers at a corporate-action cutoff, via `option.series[].markLine`
 *     (see `breakMarkerMarkLine` below for a ready-made one).
 */
export function ChartCard({
  title,
  subtitle,
  option,
  csv,
  height = 320,
  onEvents,
}: {
  title: string;
  subtitle?: string;
  option: EChartsOption;
  csv?: ChartCsvSpec;
  height?: number;
  /** Optional ECharts event handlers (e.g. `{ click: (params) => ... }`) --
   * used by the peer strip plot so clicking a dot can navigate (PLAN.md
   * §4.3 item 5). Passed straight through to `echarts-for-react`. */
  onEvents?: Record<string, (params: unknown) => void>;
}) {
  const { resolvedTheme } = useTheme();
  const chartRef = useRef<ReactECharts | null>(null);
  const theme = chartThemeFor(resolvedTheme);

  const handleDownloadPng = () => {
    const instance = chartRef.current?.getEchartsInstance();
    if (!instance) return;
    const dataUrl = instance.getDataURL({ type: "png", pixelRatio: 2, backgroundColor: "#00000000" });
    downloadPng(dataUrl, `${slugify(title)}.png`);
  };

  const handleDownloadCsv = () => {
    if (!csv) return;
    downloadCsv(csv.filename, csv.headers, csv.rows);
  };

  return (
    <div className="rounded-lg border border-border bg-surface p-4">
      <div className="mb-2 flex items-start justify-between gap-2">
        <div>
          <h3 className="text-sm font-medium">{title}</h3>
          {subtitle && <p className="text-xs text-muted">{subtitle}</p>}
        </div>
        <div className="flex shrink-0 gap-1">
          <Button variant="ghost" size="sm" onClick={handleDownloadPng} aria-label="Download PNG">
            <Download size={13} /> PNG
          </Button>
          {csv && (
            <Button variant="ghost" size="sm" onClick={handleDownloadCsv} aria-label="Download CSV">
              <Download size={13} /> CSV
            </Button>
          )}
        </div>
      </div>
      <ReactECharts
        ref={chartRef}
        option={mergeThemeDefaults(option, theme)}
        style={{ height }}
        notMerge
        opts={{ renderer: "svg" }}
        onEvents={onEvents}
      />
    </div>
  );
}

function mergeThemeDefaults(
  option: EChartsOption,
  theme: ReturnType<typeof chartThemeFor>
): EChartsOption {
  // A chart opts out of the legend entirely with an explicit `legend:
  // undefined` (e.g. the intraday price chart, which has only one
  // series) -- that key literally exists on `option` with value
  // `undefined`, which is indistinguishable from "not set" once spread
  // into an object, so it's checked here rather than relying on spread
  // order to preserve it.
  const legendExplicitlyHidden = "legend" in option && option.legend === undefined;

  return {
    backgroundColor: theme.background,
    textStyle: { color: theme.foreground, fontFamily: "inherit" },
    color: theme.series,
    // `...option` must come before the tooltip/legend merges below, not
    // after: spreading `option` last (the previous order) let a chart's
    // own `option.tooltip`/`option.legend` silently clobber these shared
    // defaults wholesale, rather than merging into them, for every chart
    // that set either key -- which is most of them.
    ...option,
    tooltip: { trigger: "axis", ...option.tooltip },
    // Shared legend defaults (UI-exploration branch bug fix): `type:
    // "scroll"` keeps the legend to a single horizontal row with
    // prev/next arrows once it runs out of width, instead of ECharts'
    // default wrap-to-multiple-lines behaviour -- a wrapped 2nd line grew
    // downward from `top` and collided with the plot area/axis labels
    // whenever a chart had more than ~4 legend entries (seen on the
    // balance-sheet Assets/Liabilities composition charts, whose category
    // count is data-driven and can't be bounded at the call site). A
    // scroll legend is always exactly one line tall, so every chart's
    // `grid.top` only has to clear one row, regardless of item count.
    legend: legendExplicitlyHidden
      ? undefined
      : {
          type: "scroll",
          itemGap: 16,
          textStyle: { color: theme.foreground },
          pageIconColor: theme.foreground,
          pageIconInactiveColor: theme.muted,
          pageTextStyle: { color: theme.foreground },
          ...option.legend,
        },
  };
}

function slugify(title: string): string {
  return title.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");
}

/** One `markLine.data` entry for a corporate-action break (demerger/
 * merger/listing cutoff) at a given x-axis position, per PLAN.md §4.0 --
 * "why a series jumps, not just that it does". Composable with other
 * markLine entries (e.g. dividend markers) in the same series' `data`
 * array, each with its own style override. */
export function breakMarkerEntry(
  theme: ReturnType<typeof chartThemeFor>,
  xValue: string | number,
  label: string
) {
  return {
    xAxis: xValue,
    lineStyle: { color: theme.muted, type: "dashed" as const, opacity: 1 },
    label: { show: true, formatter: label, color: theme.muted, fontSize: 10 },
  };
}
