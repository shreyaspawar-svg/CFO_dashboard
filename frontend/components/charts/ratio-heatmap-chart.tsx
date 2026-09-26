"use client";

import { useMemo } from "react";
import type { EChartsOption } from "echarts";
import { useTheme } from "next-themes";
import { ChartCard } from "@/components/charts/chart-card";
import { chartThemeFor } from "@/lib/chart-theme";
import { ratioGroupsFor } from "@/lib/ratio-groups";
import type { RatiosResponse } from "@/lib/api";

/** Ratio-history heatmap (PLAN.md §4.3 item 4): rows are key ratios,
 * columns are fiscal years, colour is the company's position vs the
 * sector median THAT YEAR -- with one honest simplification: this app
 * only fetches each peer's CURRENT figures (see /api/peers), not their
 * full history, so every column is coloured against today's peer median,
 * not a true year-by-year one. The value printed in each cell is always
 * the real per-year figure regardless -- only the colour is the
 * approximation, and it's a secondary channel (values are always
 * printed), per the accessibility requirement.
 *
 * Rows come from the template's OWN ratio-card groups (`ratioGroupsFor`),
 * not a fixed universal list -- a metric like NIM can come back a real,
 * non-null number for a general company too (treasury interest income),
 * but it isn't that template's headline metric and shouldn't appear on
 * its heatmap just because the backend happened to compute it. */
export function RatioHeatmapChart({
  symbol,
  template,
  ratios,
  comparableFrom,
}: {
  symbol: string;
  template: string;
  ratios: RatiosResponse;
  comparableFrom: string | null;
}) {
  const { resolvedTheme } = useTheme();
  const theme = chartThemeFor(resolvedTheme);
  const history = useMemo(() => ratios.history ?? {}, [ratios.history]);

  const candidateRows = useMemo(
    () =>
      ratioGroupsFor(template)
        .flatMap((g) => g.ratios)
        .filter((r) => r.available && r.format !== "crore")
        .map((r) => ({
          key: r.key,
          label: r.label,
          higherBetter: ratios.ratios[r.key]?.direction !== "lower_better",
        })),
    [template, ratios.ratios]
  );
  const rows = useMemo(
    () => candidateRows.filter((r) => (history[r.key] ?? []).some((p) => p.value != null)),
    [candidateRows, history]
  );
  const years = useMemo(() => {
    const allYears = new Set<string>();
    rows.forEach((r) => (history[r.key] ?? []).forEach((p) => allYears.add(p.fiscal_year)));
    return [...allYears].sort();
  }, [rows, history]);

  // Which years are pre-`comparableFrom` (e.g. TMPV's pre-demerger years) --
  // marked with "*" on the axis rather than silently presented alongside
  // comparable years as if the whole row were one continuous trend (the
  // same "show it, mark the discontinuity" convention as the price and
  // income-statement charts' break markers).
  const nonComparableYears = useMemo(() => {
    if (!comparableFrom) return new Set<string>();
    const set = new Set<string>();
    rows.forEach((r) =>
      (history[r.key] ?? []).forEach((p) => {
        if (p.period_end < comparableFrom) set.add(p.fiscal_year);
      })
    );
    return set;
  }, [rows, history, comparableFrom]);

  const option = useMemo<EChartsOption | null>(() => {
    if (rows.length === 0 || years.length === 0) return null;
    const cells: { value: [number, number, number]; label: string }[] = [];
    let maxAbsScore = 1;

    rows.forEach((row, rowIdx) => {
      const median = ratios.ratios[row.key]?.peer_median;
      const points = history[row.key] ?? [];
      years.forEach((year, yearIdx) => {
        const point = points.find((p) => p.fiscal_year === year);
        if (!point || point.value == null) return;
        let score = 0;
        if (median != null && median !== 0) {
          score = ((point.value - median) / Math.abs(median)) * 100;
          if (!row.higherBetter) score = -score;
        }
        maxAbsScore = Math.max(maxAbsScore, Math.abs(score));
        cells.push({ value: [yearIdx, rowIdx, score], label: point.value.toFixed(1) });
      });
    });

    return {
      grid: { left: 140, right: 16, top: 16, bottom: 40 },
      xAxis: {
        type: "category",
        data: years,
        axisLabel: {
          color: theme.muted,
          formatter: (year: string) => (nonComparableYears.has(year) ? `${year}*` : year),
        },
        splitArea: { show: true },
      },
      yAxis: { type: "category", data: rows.map((r) => r.label), axisLabel: { color: theme.muted } },
      visualMap: {
        min: -maxAbsScore,
        max: maxAbsScore,
        show: false,
        inRange: { color: [theme.down, theme.border, theme.up] },
      },
      series: [
        {
          type: "heatmap",
          data: cells.map((c) => c.value),
          label: {
            show: true,
            color: theme.foreground,
            formatter: (params: unknown) => {
              const p = params as { dataIndex: number };
              return cells[p.dataIndex]?.label ?? "";
            },
          },
        },
      ],
    };
  }, [rows, years, ratios, history, theme, nonComparableYears]);

  if (!option) {
    return (
      <div className="flex h-72 items-center justify-center rounded-lg border border-border bg-surface text-sm text-muted">
        Not enough ratio history for a heatmap.
      </div>
    );
  }

  return (
    <ChartCard
      title="Ratio history vs sector"
      subtitle={
        "Colour: today's peer median (a true per-year peer median isn't available from this data source) · " +
        "value is always the real per-year figure" +
        (nonComparableYears.size > 0 ? " · * = pre-corporate-action, not comparable (see banner above)" : "")
      }
      option={option}
      height={Math.max(220, rows.length * 40 + 80)}
      csv={{
        filename: `${symbol}_ratio_heatmap.csv`,
        headers: ["Ratio", ...years],
        rows: rows.map((row) => [
          row.label,
          ...years.map((year) => (history[row.key] ?? []).find((p) => p.fiscal_year === year)?.value ?? null),
        ]),
      }}
    />
  );
}
