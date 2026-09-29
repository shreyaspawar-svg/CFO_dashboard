"use client";

import { useMemo, useState } from "react";
import type { EChartsOption } from "echarts";
import { useTheme } from "next-themes";
import { AlertTriangle, Check } from "lucide-react";
import { useFinancials, useRatios } from "@/lib/queries";
import { ChartCard, breakMarkerEntry } from "@/components/charts/chart-card";
import { chartThemeFor } from "@/lib/chart-theme";
import type { BalanceSheetPeriodDetail } from "@/lib/api";
import { cn } from "@/lib/utils";

const FINANCIAL_TEMPLATES = new Set(["bank", "nbfc", "insurance"]);
const BALANCE_CHECK_TOLERANCE_PCT = 0.5;

function useCutoffIndex(periods: BalanceSheetPeriodDetail[], comparableFrom: string | null) {
  return comparableFrom ? periods.findIndex((p) => p.period_end >= comparableFrom) : -1;
}

function StackedComposition({
  title,
  periods,
  keyOf,
  theme,
  comparableFrom,
  csvName,
}: {
  title: string;
  periods: BalanceSheetPeriodDetail[];
  keyOf: (p: BalanceSheetPeriodDetail) => Record<string, number | null>;
  theme: ReturnType<typeof chartThemeFor>;
  comparableFrom: string | null;
  csvName: string;
}) {
  const cutoffIndex = useCutoffIndex(periods, comparableFrom);
  const categories = useMemo(() => {
    const keys = new Set<string>();
    periods.forEach((p) => Object.keys(keyOf(p)).forEach((k) => keys.add(k)));
    return [...keys];
  }, [periods, keyOf]);

  const option: EChartsOption = {
    grid: { left: 64, right: 16, top: 48, bottom: 40 },
    legend: { top: 0, left: "center", data: categories },
    xAxis: { type: "category", data: periods.map((p) => p.fiscal_year), axisLabel: { color: theme.muted } },
    yAxis: { type: "value", name: "₹ Cr", axisLabel: { color: theme.muted } },
    series: categories.map((cat, i) => ({
      name: cat,
      type: "bar" as const,
      stack: "total",
      data: periods.map((p) => keyOf(p)[cat] ?? null),
      markLine:
        i === 0 && cutoffIndex > 0
          ? {
              symbol: "none",
              silent: true,
              lineStyle: { color: theme.muted, type: "dashed" as const },
              label: { show: false },
              data: [breakMarkerEntry(theme, periods[cutoffIndex].fiscal_year, "Not comparable before this period")],
            }
          : undefined,
    })),
  };

  return (
    <ChartCard
      title={title}
      option={option}
      height={300}
      csv={{
        filename: csvName,
        headers: ["Period", ...categories],
        rows: periods.map((p) => [p.fiscal_year, ...categories.map((c) => keyOf(p)[c] ?? null)]),
      }}
    />
  );
}

function CompositionTreemap({ period, theme }: { period: BalanceSheetPeriodDetail; theme: ReturnType<typeof chartThemeFor> }) {
  const data = Object.entries(period.assets)
    .filter(([, v]) => v != null && v !== 0)
    .map(([name, value]) => ({ name, value: Math.abs(value as number) }));
  const option: EChartsOption = {
    series: [
      {
        type: "treemap",
        data,
        label: { color: theme.foreground, formatter: "{b}" },
        breadcrumb: { show: false },
      },
    ],
  };
  if (data.length === 0) {
    return <div className="flex h-64 items-center justify-center rounded-lg border border-border bg-surface text-sm text-muted">No data.</div>;
  }
  return <ChartCard title={`Asset composition, ${period.fiscal_year}`} option={option} height={260} />;
}

export function BalanceSheetTab({ symbol, template }: { symbol: string; template: string }) {
  const [periodKind, setPeriodKind] = useState<"annual" | "quarterly">("annual");
  const { data: financials, isLoading } = useFinancials(symbol, periodKind);
  const { data: ratios } = useRatios(symbol);
  const { resolvedTheme } = useTheme();
  const theme = chartThemeFor(resolvedTheme);

  const periods = financials?.balance_sheet_detail ?? [];
  const rHistory = ratios?.history;
  const comparableFrom = financials?.comparable_from ?? null;
  const isFinancial = FINANCIAL_TEMPLATES.has(template);
  const latest = periods.length > 0 ? periods[periods.length - 1] : null;

  if (isLoading || !financials) {
    return <div className="h-80 animate-pulse rounded-lg border border-border bg-surface" />;
  }
  if (periods.length === 0) {
    return <p className="text-sm text-muted">No comparable balance sheet periods available.</p>;
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-1" role="tablist" aria-label="Statement period">
        {(["annual", "quarterly"] as const).map((kind) => (
          <button
            key={kind}
            role="tab"
            aria-selected={periodKind === kind}
            onClick={() => setPeriodKind(kind)}
            className={cn(
              "rounded-md border px-3 py-1 text-xs capitalize transition-colors",
              periodKind === kind ? "border-accent bg-accent/10 text-accent" : "border-border text-muted hover:text-foreground"
            )}
          >
            {kind}
          </button>
        ))}
      </div>

      {latest && (
        <div className="flex items-center gap-2 rounded-lg border border-border bg-surface p-3 text-sm">
          {latest.balance_check_pct != null && latest.balance_check_pct <= BALANCE_CHECK_TOLERANCE_PCT ? (
            <Check size={16} className="text-up" />
          ) : (
            <AlertTriangle size={16} className="text-amber-500" />
          )}
          <span>
            Balance check ({latest.fiscal_year}): Assets vs Liabilities+Equity gap{" "}
            {latest.balance_check_pct != null ? `${latest.balance_check_pct.toFixed(2)}%` : "—"}
            {latest.balance_check_pct != null && latest.balance_check_pct > BALANCE_CHECK_TOLERANCE_PCT
              ? " (exceeds the 0.5% comfort tolerance -- a free-source reporting-basis gap, not a bug in this app's arithmetic)"
              : ""}
          </span>
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <StackedComposition
          title="Assets"
          periods={periods}
          keyOf={(p) => p.assets}
          theme={theme}
          comparableFrom={comparableFrom}
          csvName={`${symbol}_assets.csv`}
        />
        <StackedComposition
          title="Liabilities & Equity"
          periods={periods}
          keyOf={(p) => p.liabilities_equity}
          theme={theme}
          comparableFrom={comparableFrom}
          csvName={`${symbol}_liabilities_equity.csv`}
        />
      </div>

      {latest && <CompositionTreemap period={latest} theme={theme} />}

      {!isFinancial && (
        <ChartCard
          title="Debt vs cash, and net debt"
          subtitle="Not shown for financial-company templates"
          option={{
            grid: { left: 64, right: 56, top: 32, bottom: 40 },
            legend: { top: 0, left: "center", data: ["Total debt", "Cash & equivalents", "Net debt/(cash)"] },
            xAxis: { type: "category", data: periods.map((p) => p.fiscal_year), axisLabel: { color: theme.muted } },
            yAxis: [
              { type: "value", name: "₹ Cr", axisLabel: { color: theme.muted } },
              { type: "value", name: "₹ Cr", axisLabel: { color: theme.muted }, splitLine: { show: false } },
            ],
            series: [
              { name: "Total debt", type: "bar", data: periods.map((p) => p.liabilities_equity["Debt"] ?? null) },
              { name: "Cash & equivalents", type: "bar", data: periods.map((p) => p.assets["Cash & equivalents"] ?? null) },
              {
                name: "Net debt/(cash)",
                type: "line",
                yAxisIndex: 1,
                data: periods.map((p) => p.net_debt),
              },
            ],
          }}
          height={280}
          csv={{
            filename: `${symbol}_debt_cash.csv`,
            headers: ["Period", "Debt", "Cash", "Net debt"],
            rows: periods.map((p) => [p.fiscal_year, p.liabilities_equity["Debt"] ?? null, p.assets["Cash & equivalents"] ?? null, p.net_debt]),
          }}
        />
      )}

      <ChartCard
        title="Equity & book value per share"
        option={{
          grid: { left: 64, right: 56, top: 40, bottom: 40 },
          legend: { top: 0, left: "center", data: ["Equity", "BVPS"] },
          xAxis: { type: "category", data: periods.map((p) => p.fiscal_year), axisLabel: { color: theme.muted } },
          yAxis: [
            { type: "value", name: "₹ Cr", axisLabel: { color: theme.muted } },
            { type: "value", name: "₹/share", axisLabel: { color: theme.muted }, splitLine: { show: false } },
          ],
          series: [
            { name: "Equity", type: "bar", data: periods.map((p) => p.liabilities_equity["Equity"] ?? null) },
            { name: "BVPS", type: "line", yAxisIndex: 1, data: periods.map((p) => p.bvps) },
          ],
        }}
        height={260}
        csv={{
          filename: `${symbol}_equity_bvps.csv`,
          headers: ["Period", "Equity", "BVPS"],
          rows: periods.map((p) => [p.fiscal_year, p.liabilities_equity["Equity"] ?? null, p.bvps]),
        }}
      />

      {template === "general" && rHistory && (
        <ChartCard
          title="Working-capital days & cash conversion cycle"
          subtitle="From annual comparable periods (not affected by the Annual/Quarterly toggle above)"
          option={{
            grid: { left: 56, right: 16, top: 40, bottom: 40 },
            legend: { top: 0, left: "center", data: ["Debtor days", "Inventory days", "Payable days", "CCC"] },
            xAxis: {
              type: "category",
              data: (rHistory["debtor_days"] ?? []).map((p) => p.fiscal_year),
              axisLabel: { color: theme.muted },
            },
            yAxis: { type: "value", name: "Days", axisLabel: { color: theme.muted } },
            series: [
              { name: "Debtor days", type: "line", data: (rHistory["debtor_days"] ?? []).map((p) => p.value) },
              { name: "Inventory days", type: "line", data: (rHistory["inventory_days"] ?? []).map((p) => p.value) },
              { name: "Payable days", type: "line", data: (rHistory["payable_days"] ?? []).map((p) => p.value) },
              { name: "CCC", type: "line", data: (rHistory["cash_conversion_cycle"] ?? []).map((p) => p.value) },
            ],
          }}
          height={260}
          csv={{
            filename: `${symbol}_working_capital_days.csv`,
            headers: ["Period", "Debtor days", "Inventory days", "Payable days", "CCC"],
            rows: (rHistory["debtor_days"] ?? []).map((p, i) => [
              p.fiscal_year,
              p.value,
              (rHistory["inventory_days"] ?? [])[i]?.value ?? null,
              (rHistory["payable_days"] ?? [])[i]?.value ?? null,
              (rHistory["cash_conversion_cycle"] ?? [])[i]?.value ?? null,
            ]),
          }}
        />
      )}
    </div>
  );
}
