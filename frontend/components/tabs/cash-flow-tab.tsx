"use client";

import { useMemo, useState } from "react";
import type { EChartsOption } from "echarts";
import { useTheme } from "next-themes";
import { useFinancials } from "@/lib/queries";
import { ChartCard } from "@/components/charts/chart-card";
import { chartThemeFor } from "@/lib/chart-theme";
import { cn } from "@/lib/utils";

const BANK_TEMPLATES = new Set(["bank", "nbfc"]);

export function CashFlowTab({ symbol, template }: { symbol: string; template: string }) {
  const isBank = BANK_TEMPLATES.has(template);
  const isInsurance = template === "insurance";
  const [periodKind, setPeriodKind] = useState<"annual" | "quarterly">("annual");
  const { data: financials, isLoading } = useFinancials(symbol, isInsurance ? "annual" : periodKind);
  const { resolvedTheme } = useTheme();
  const theme = chartThemeFor(resolvedTheme);

  const sankey = financials?.cash_flow_sankey;

  const combo = useMemo(() => {
    const cashPeriods = financials?.cash_flow ?? [];
    const detail = financials?.cash_flow_detail ?? [];
    return cashPeriods.map((p, i) => ({
      fiscal_year: p.fiscal_year,
      cfo: p.line_items.cfo ?? null,
      cfi: p.line_items.cfi ?? null,
      cff: p.line_items.cff ?? null,
      net_change:
        p.line_items.cfo != null && p.line_items.cfi != null && p.line_items.cff != null
          ? p.line_items.cfo + p.line_items.cfi + p.line_items.cff
          : null,
      fcf: p.line_items.free_cash_flow ?? null,
      fcf_margin: detail[i]?.fcf_margin_pct ?? null,
      cfo_to_ebitda: detail[i]?.cfo_to_ebitda ?? null,
      cfo_to_pat: detail[i]?.cfo_to_pat ?? null,
    }));
  }, [financials]);

  if (isLoading || !financials) {
    return <div className="h-80 animate-pulse rounded-lg border border-border bg-surface" />;
  }
  if (combo.length === 0) {
    return <p className="text-sm text-muted">No comparable cash flow periods available.</p>;
  }

  const cfoOption: EChartsOption = {
    grid: { left: 64, right: 16, top: 40, bottom: 40 },
    legend: { top: 0, left: "center", data: ["CFO", "CFI", "CFF", "Net change in cash"] },
    xAxis: { type: "category", data: combo.map((c) => c.fiscal_year), axisLabel: { color: theme.muted } },
    yAxis: { type: "value", name: "₹ Cr", axisLabel: { color: theme.muted } },
    series: [
      { name: "CFO", type: "bar", data: combo.map((c) => c.cfo) },
      { name: "CFI", type: "bar", data: combo.map((c) => c.cfi) },
      { name: "CFF", type: "bar", data: combo.map((c) => c.cff) },
      { name: "Net change in cash", type: "line", data: combo.map((c) => c.net_change) },
    ],
  };
  const cfoChart = (
    <ChartCard
      title="CFO / CFI / CFF and net change in cash"
      option={cfoOption}
      height={300}
      csv={{
        filename: `${symbol}_cash_flow.csv`,
        headers: ["Period", "CFO", "CFI", "CFF", "Net change in cash"],
        rows: combo.map((c) => [c.fiscal_year, c.cfo, c.cfi, c.cff, c.net_change]),
      }}
    />
  );

  if (isBank) {
    return (
      <div className="space-y-4">
        <div className="rounded-lg border border-amber-500/40 bg-amber-500/10 p-3 text-sm">
          Bank cash flows mostly reflect deposit/loan movements, not the same operating/investing/financing
          story as a general company -- shown here for reference, not as a leverage or liquidity signal.
        </div>
        {cfoChart}
        <div className="overflow-x-auto rounded-lg border border-border bg-surface p-4">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-xs text-muted">
                <th className="py-1.5 pr-4 font-normal">Period</th>
                <th className="py-1.5 px-2 text-right font-normal">CFO</th>
                <th className="py-1.5 px-2 text-right font-normal">CFI</th>
                <th className="py-1.5 px-2 text-right font-normal">CFF</th>
              </tr>
            </thead>
            <tbody>
              {combo.map((c) => (
                <tr key={c.fiscal_year} className="border-b border-border/50">
                  <td className="py-1.5 pr-4">{c.fiscal_year}</td>
                  <td className="py-1.5 px-2 text-right tabular-nums-fixed">{c.cfo ?? "—"}</td>
                  <td className="py-1.5 px-2 text-right tabular-nums-fixed">{c.cfi ?? "—"}</td>
                  <td className="py-1.5 px-2 text-right tabular-nums-fixed">{c.cff ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    );
  }

  const sankeyOption: EChartsOption | null =
    sankey && sankey.links.length > 0
      ? {
          series: [
            {
              type: "sankey",
              data: [...new Set(sankey.links.flatMap((l) => [l.source, l.target]))].map((name) => ({
                name,
                itemStyle: { color: name.startsWith("Other") ? theme.muted : theme.accent },
              })),
              links: sankey.links,
              label: { color: theme.foreground },
              lineStyle: { color: "gradient", curveness: 0.5 },
            },
          ],
        }
      : null;

  return (
    <div className="space-y-4">
      {!isInsurance && (
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
      )}

      {cfoChart}

      <ChartCard
        title="Free cash flow & FCF margin"
        option={{
          grid: { left: 64, right: 56, top: 40, bottom: 40 },
          legend: { top: 0, left: "center", data: ["FCF", "FCF margin"] },
          xAxis: { type: "category", data: combo.map((c) => c.fiscal_year), axisLabel: { color: theme.muted } },
          yAxis: [
            { type: "value", name: "₹ Cr", axisLabel: { color: theme.muted } },
            { type: "value", name: "%", axisLabel: { color: theme.muted }, splitLine: { show: false } },
          ],
          series: [
            { name: "FCF", type: "bar", data: combo.map((c) => c.fcf) },
            { name: "FCF margin", type: "line", yAxisIndex: 1, data: combo.map((c) => c.fcf_margin) },
          ],
        }}
        height={280}
        csv={{
          filename: `${symbol}_fcf.csv`,
          headers: ["Period", "FCF", "FCF margin %"],
          rows: combo.map((c) => [c.fiscal_year, c.fcf, c.fcf_margin]),
        }}
      />

      <ChartCard
        title="Cash conversion: CFO/EBITDA & CFO/PAT"
        subtitle="Reference line at 1.0x"
        option={{
          grid: { left: 56, right: 16, top: 40, bottom: 40 },
          legend: { top: 0, left: "center", data: ["CFO/EBITDA", "CFO/PAT"] },
          xAxis: { type: "category", data: combo.map((c) => c.fiscal_year), axisLabel: { color: theme.muted } },
          yAxis: { type: "value", name: "x", axisLabel: { color: theme.muted } },
          series: [
            {
              name: "CFO/EBITDA",
              type: "line",
              data: combo.map((c) => c.cfo_to_ebitda),
              markLine: { symbol: "none", data: [{ yAxis: 1, label: { formatter: "1.0x" } }], lineStyle: { color: theme.muted, type: "dashed" } },
            },
            { name: "CFO/PAT", type: "line", data: combo.map((c) => c.cfo_to_pat) },
          ],
        }}
        height={260}
        csv={{
          filename: `${symbol}_cash_conversion.csv`,
          headers: ["Period", "CFO/EBITDA", "CFO/PAT"],
          rows: combo.map((c) => [c.fiscal_year, c.cfo_to_ebitda, c.cfo_to_pat]),
        }}
      />

      {sankeyOption ? (
        <ChartCard
          title={`Cash flow sources -> uses, ${combo[combo.length - 1]?.fiscal_year ?? ""}`}
          subtitle={
            sankey?.gap != null
              ? `Reconciles CFO+CFI+CFF to the reported change in cash (gap ${sankey.gap >= 0 ? "+" : ""}${sankey.gap.toFixed(1)} Cr, shown as "Other")`
              : undefined
          }
          option={sankeyOption}
          height={280}
        />
      ) : (
        <div className="flex h-72 items-center justify-center rounded-lg border border-border bg-surface text-sm text-muted">
          Not enough cash flow data for a Sankey this period.
        </div>
      )}
    </div>
  );
}
