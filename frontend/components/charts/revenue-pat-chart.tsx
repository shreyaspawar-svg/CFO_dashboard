"use client";

import { useMemo } from "react";
import type { EChartsOption } from "echarts";
import { useTheme } from "next-themes";
import { ChartCard } from "@/components/charts/chart-card";
import { chartThemeFor } from "@/lib/chart-theme";
import { useFinancials, useRatios } from "@/lib/queries";
import { marginPct } from "@/lib/income-statement";

const BANK_TEMPLATES = new Set(["bank", "nbfc"]);

/** Last 4 FY + TTM grouped bars for the top-line metric (Revenue / NII /
 * Premiums, template-aware) and PAT, with a margin % line on the right
 * axis (PLAN.md Phase 5.1 item 3 -- replaces the "Financial snapshot"
 * panel, which used to just duplicate the KPI row verbatim). */
export function RevenuePatChart({ symbol, template }: { symbol: string; template: string }) {
  const { data: financials, isLoading: financialsLoading } = useFinancials(symbol, "annual");
  const { data: ratios, isLoading: ratiosLoading } = useRatios(symbol);
  const { resolvedTheme } = useTheme();
  const theme = chartThemeFor(resolvedTheme);

  const isBank = BANK_TEMPLATES.has(template);
  const isInsurance = template === "insurance";
  const primaryKey = isBank ? "net_interest_income" : isInsurance ? "premiums_earned" : "revenue";
  const primaryLabel = isBank ? "NII" : isInsurance ? "Premiums" : "Revenue";
  const ttmKey = isBank ? "ttm_net_interest_income" : isInsurance ? "ttm_premiums_earned" : "ttm_revenue";

  const series = useMemo(() => {
    const periods = (financials?.income_statement ?? []).slice(-4);
    const labels = periods.map((p) => p.fiscal_year);
    const primary = periods.map((p) => p.line_items[primaryKey] ?? null);
    const pat = periods.map((p) => p.line_items.net_income ?? null);
    const margin = periods.map((p) => marginPct(p.line_items.net_income, p.line_items[primaryKey]));

    const ttmPrimary = ratios?.ratios[ttmKey]?.value ?? null;
    const ttmPat = ratios?.ratios["ttm_net_income"]?.value ?? null;
    const ttmMargin = marginPct(ttmPat, ttmPrimary);

    return {
      labels: [...labels, "TTM"],
      primary: [...primary, ttmPrimary],
      pat: [...pat, ttmPat],
      margin: [...margin, ttmMargin],
    };
  }, [financials, ratios, primaryKey, ttmKey]);

  const hasData = series.primary.some((v) => v !== null) || series.pat.some((v) => v !== null);

  const option = useMemo<EChartsOption | null>(() => {
    if (!hasData) return null;
    return {
      grid: { left: 64, right: 56, top: 40, bottom: 40 },
      legend: { top: 0, left: "center", data: [primaryLabel, "PAT", "PAT margin"] },
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
        { name: primaryLabel, type: "bar", data: series.primary },
        { name: "PAT", type: "bar", data: series.pat },
        { name: "PAT margin", type: "line", yAxisIndex: 1, data: series.margin, showSymbol: false },
      ],
    };
  }, [hasData, series, theme, primaryLabel]);

  if (financialsLoading || ratiosLoading) {
    return <div className="h-80 animate-pulse rounded-lg border border-border bg-surface" />;
  }
  if (!option) {
    return <p className="text-sm text-muted">Not enough data for a financial snapshot.</p>;
  }

  return (
    <ChartCard
      title={`${primaryLabel} & PAT, last 4 FY + TTM`}
      subtitle="Bars: ₹ Cr (left axis) · Line: PAT margin % (right axis)"
      option={option}
      height={320}
      csv={{
        filename: `${symbol}_financial_snapshot.csv`,
        headers: ["Period", primaryLabel, "PAT", "PAT margin %"],
        rows: series.labels.map((label, i) => [label, series.primary[i], series.pat[i], series.margin[i]]),
      }}
    />
  );
}
