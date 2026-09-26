"use client";

import { useMemo } from "react";
import type { EChartsOption } from "echarts";
import { useTheme } from "next-themes";
import { ChartCard, breakMarkerEntry } from "@/components/charts/chart-card";
import { chartThemeFor } from "@/lib/chart-theme";
import { formatMultiple, formatPercent } from "@/lib/format";
import type { RatiosResponse } from "@/lib/api";

/** DuPont decomposition (PLAN.md §4.3 item 3): a grouped bar chart of the
 * factors across years, plus a latest-year "equation" strip. Two shapes,
 * chosen by `dupont_kind` (from the backend, not re-derived here):
 * "general" (margin x turnover x leverage) or "bank" (ROA x leverage). */
export function DupontChart({
  symbol,
  ratios,
  comparableFrom,
  template,
}: {
  symbol: string;
  ratios: RatiosResponse;
  comparableFrom: string | null;
  template: string;
}) {
  const { resolvedTheme } = useTheme();
  const theme = chartThemeFor(resolvedTheme);
  const isBank = ratios.dupont_kind === "bank";

  const series = useMemo(() => {
    const history = ratios.history ?? {};
    const marginKey = isBank ? "roa" : "pat_margin";
    const marginPoints = history[marginKey] ?? [];
    const leveragePoints = history["equity_multiplier"] ?? [];
    const turnoverPoints = isBank ? [] : history["asset_turnover"] ?? [];
    const cutoffIndex = comparableFrom ? marginPoints.findIndex((p) => p.period_end >= comparableFrom) : -1;
    return {
      labels: marginPoints.map((p) => p.fiscal_year),
      margin: marginPoints.map((p) => p.value),
      leverage: leveragePoints.map((p) => p.value),
      turnover: turnoverPoints.map((p) => p.value),
      cutoffIndex,
    };
  }, [ratios, isBank, comparableFrom]);

  const option = useMemo<EChartsOption | null>(() => {
    if (series.labels.length === 0) return null;
    const marginSeries = {
      name: isBank ? "ROA %" : "PAT margin %",
      type: "bar" as const,
      data: series.margin,
      markLine:
        series.cutoffIndex > 0
          ? {
              symbol: "none",
              silent: true,
              lineStyle: { color: theme.muted, type: "dashed" as const },
              label: { show: false },
              data: [breakMarkerEntry(theme, series.labels[series.cutoffIndex], "Not comparable before this period")],
            }
          : undefined,
    };
    const leverageSeries = {
      name: isBank ? "Leverage (Assets/Equity)" : "Equity multiplier",
      type: "bar" as const,
      yAxisIndex: 1,
      data: series.leverage,
    };
    const barSeries = isBank
      ? [marginSeries, leverageSeries]
      : [
          marginSeries,
          { name: "Asset turnover", type: "bar" as const, yAxisIndex: 1, data: series.turnover },
          leverageSeries,
        ];
    return {
      grid: { left: 56, right: 56, top: 40, bottom: 40 },
      legend: { top: 0, left: "center", data: barSeries.map((s) => s.name) },
      xAxis: { type: "category", data: series.labels, axisLabel: { color: theme.muted } },
      yAxis: [
        { type: "value", name: isBank ? "ROA %" : "Margin %", axisLabel: { color: theme.muted } },
        { type: "value", name: "x", axisLabel: { color: theme.muted }, splitLine: { show: false } },
      ],
      series: barSeries,
    };
  }, [series, theme, isBank]);

  const latest = {
    margin: series.margin.at(-1) ?? null,
    turnover: series.turnover.at(-1) ?? null,
    leverage: series.leverage.at(-1) ?? null,
    roe: ratios.ratios.roe?.value ?? null,
    dupontRoe: ratios.ratios.dupont_roe_check_pct?.value ?? null,
  };

  return (
    <div className="space-y-3">
      {option ? (
        <ChartCard
          title="DuPont decomposition"
          subtitle={
            isBank
              ? "ROE = ROA x Leverage"
              : template === "insurance"
                ? "ROE = PAT margin x Asset turnover x Equity multiplier (3-step, general form)"
                : "ROE = PAT margin x Asset turnover x Equity multiplier"
          }
          option={option}
          height={280}
          csv={{
            filename: `${symbol}_dupont.csv`,
            headers: isBank
              ? ["Period", "ROA %", "Leverage"]
              : ["Period", "PAT margin %", "Asset turnover", "Equity multiplier"],
            rows: series.labels.map((label, i) =>
              isBank
                ? [label, series.margin[i], series.leverage[i]]
                : [label, series.margin[i], series.turnover[i], series.leverage[i]]
            ),
          }}
        />
      ) : (
        <div className="flex h-72 items-center justify-center rounded-lg border border-border bg-surface text-sm text-muted">
          Not enough data for a DuPont decomposition.
        </div>
      )}

      <div className="rounded-lg border border-border bg-surface p-3 text-sm">
        <div className="flex flex-wrap items-center gap-2 tabular-nums-fixed">
          {isBank ? (
            <>
              <span className="font-semibold">{formatPercent(latest.margin)}</span>
              <span className="text-muted">(ROA)</span>
              <span className="text-muted">x</span>
              <span className="font-semibold">{formatMultiple(latest.leverage)}</span>
              <span className="text-muted">(Leverage)</span>
            </>
          ) : (
            <>
              <span className="font-semibold">{formatPercent(latest.margin)}</span>
              <span className="text-muted">(margin)</span>
              <span className="text-muted">x</span>
              <span className="font-semibold">{formatMultiple(latest.turnover)}</span>
              <span className="text-muted">(turnover)</span>
              <span className="text-muted">x</span>
              <span className="font-semibold">{formatMultiple(latest.leverage)}</span>
              <span className="text-muted">(equity multiplier)</span>
            </>
          )}
          <span className="text-muted">=</span>
          <span className="font-semibold text-accent">{formatPercent(latest.dupontRoe)}</span>
          <span className="text-muted">(DuPont ROE)</span>
        </div>
        <p className="mt-1 text-xs text-muted">
          Card ROE: {formatPercent(latest.roe)}
          {ratios.dupont_reconciliation_gap_pp != null && (
            <>
              {" "}
              &middot; gap:{" "}
              {ratios.dupont_reconciliation_gap_pp < 0.005
                ? "reconciles exactly"
                : `${ratios.dupont_reconciliation_gap_pp.toFixed(2)}pp`}
            </>
          )}
        </p>
      </div>
    </div>
  );
}
