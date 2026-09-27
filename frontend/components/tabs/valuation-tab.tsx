"use client";

import { useMemo, useState } from "react";
import type { EChartsOption } from "echarts";
import { useTheme } from "next-themes";
import { useQuote, usePeers, useValuation } from "@/lib/queries";
import { ChartCard } from "@/components/charts/chart-card";
import { chartThemeFor } from "@/lib/chart-theme";
import { formatMultiple, formatPercent, formatRupees, MISSING_VALUE_PLACEHOLDER } from "@/lib/format";

const FINANCIAL_TEMPLATES = new Set(["bank", "nbfc", "insurance"]);

const MULTIPLE_LABELS: Record<string, string> = {
  pe: "P/E",
  pb: "P/B",
  ev_ebitda: "EV/EBITDA",
  ev_sales: "EV/Sales",
  peg: "PEG",
  dividend_yield: "Dividend yield",
  earnings_yield: "Earnings yield",
  payout_ratio: "Payout ratio",
};
const GENERAL_MULTIPLES = ["pe", "pb", "ev_ebitda", "ev_sales", "peg", "dividend_yield", "earnings_yield"];
const FINANCIAL_MULTIPLES = ["pe", "pb", "dividend_yield"];

function Slider({
  label,
  value,
  onChange,
  min,
  max,
  step,
  suffix,
}: {
  label: string;
  value: number;
  onChange: (v: number) => void;
  min: number;
  max: number;
  step: number;
  suffix: string;
}) {
  return (
    <label className="block text-xs">
      <span className="flex items-center justify-between text-muted">
        <span>{label}</span>
        <span className="font-medium text-foreground">
          {value.toFixed(1)}
          {suffix}
        </span>
      </span>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="mt-1 w-full accent-accent"
      />
    </label>
  );
}

export function ValuationTab({ symbol, template }: { symbol: string; template: string }) {
  const isFinancial = FINANCIAL_TEMPLATES.has(template);
  const [growthPct, setGrowthPct] = useState<number | null>(null);
  const [waccPct, setWaccPct] = useState(12);
  const [terminalGrowthPct, setTerminalGrowthPct] = useState(4);

  const { data: valuation, isLoading } = useValuation(symbol, {
    growthRatePct: growthPct ?? undefined,
    waccPct,
    terminalGrowthPct,
  });
  const { data: quote } = useQuote(symbol);
  const { data: peers } = usePeers(symbol);
  const { resolvedTheme } = useTheme();
  const theme = chartThemeFor(resolvedTheme);

  const multipleKeys = isFinancial ? FINANCIAL_MULTIPLES : GENERAL_MULTIPLES;

  const peBand = useMemo(() => valuation?.pe_band ?? [], [valuation]);
  const pbBand = useMemo(() => valuation?.pb_band ?? [], [valuation]);

  const bandOption = useMemo<EChartsOption | null>(() => {
    if (peBand.length === 0) return null;
    return {
      grid: { left: 56, right: 16, top: 40, bottom: 40 },
      legend: { top: 0, left: "center", data: ["P/E", "P/B"] },
      xAxis: { type: "category", data: peBand.map((p) => p.date), axisLabel: { color: theme.muted, show: false } },
      yAxis: [
        { type: "value", name: "P/E (x)", axisLabel: { color: theme.muted } },
        { type: "value", name: "P/B (x)", axisLabel: { color: theme.muted }, splitLine: { show: false } },
      ],
      series: [
        { name: "P/E", type: "line", showSymbol: false, data: peBand.map((p) => p.pe) },
        {
          name: "P/B",
          type: "line",
          showSymbol: false,
          yAxisIndex: 1,
          data: pbBand.map((p) => p.pb),
        },
      ],
    };
  }, [peBand, pbBand, theme]);

  const pbRoeScatter = useMemo<EChartsOption | null>(() => {
    if (!isFinancial || !peers) return null;
    const points = peers.peers
      .map((p) => ({ symbol: p.symbol, pb: p.metrics.pb, roe: p.metrics.roe }))
      .filter((p): p is { symbol: string; pb: number; roe: number } => p.pb != null && p.roe != null);
    if (points.length === 0) return null;
    return {
      grid: { left: 56, right: 16, top: 24, bottom: 40 },
      xAxis: { type: "value", name: "ROE %", axisLabel: { color: theme.muted } },
      yAxis: { type: "value", name: "P/B (x)", axisLabel: { color: theme.muted } },
      series: [
        {
          type: "scatter",
          symbolSize: 14,
          data: points.map((p) => [p.roe, p.pb, p.symbol]),
          itemStyle: {
            color: (params: { data: unknown }) =>
              Array.isArray(params.data) && params.data[2] === symbol ? theme.accent : theme.muted,
          },
          label: {
            show: true,
            formatter: (params: { data: unknown }) => String((params.data as unknown[])[2]),
            position: "top",
            color: theme.foreground,
          },
        },
      ],
    } as EChartsOption;
  }, [isFinancial, peers, theme, symbol]);

  if (isLoading || !valuation) {
    return <div className="h-80 animate-pulse rounded-lg border border-border bg-surface" />;
  }

  const ltp = quote?.last_price ?? null;
  const intrinsic = valuation.dcf.intrinsic_value_per_share;
  const upsidePct = ltp != null && intrinsic != null ? ((intrinsic - ltp) / ltp) * 100 : null;

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {multipleKeys.map((key) => {
          const detail = valuation.multiples_detail[key];
          const isPercentKey = key === "dividend_yield" || key === "earnings_yield" || key === "payout_ratio";
          const fmt = isPercentKey ? formatPercent : formatMultiple;
          return (
            <div key={key} className="rounded-lg border border-border bg-surface p-3">
              <p className="text-xs text-muted">{MULTIPLE_LABELS[key]}</p>
              <p className="text-lg font-semibold tabular-nums-fixed">{fmt(detail?.value ?? null)}</p>
              <p className="text-xs text-muted">
                Median {fmt(detail?.peer_median ?? null)}
                {detail?.percentile != null ? ` · ${detail.percentile.toFixed(0)}th pct` : ""}
              </p>
            </div>
          );
        })}
      </div>

      {bandOption ? (
        <ChartCard
          title="Historical P/E and P/B band"
          subtitle={
            valuation.pe_band_summary
              ? `P/E: min ${formatMultiple(valuation.pe_band_summary.min)} · median ${formatMultiple(
                  valuation.pe_band_summary.median
                )} · max ${formatMultiple(valuation.pe_band_summary.max)} · current ${formatMultiple(
                  valuation.pe_band_summary.current
                )}`
              : undefined
          }
          option={bandOption}
          height={300}
          csv={{
            filename: `${symbol}_pe_pb_band.csv`,
            headers: ["Date", "P/E", "P/B"],
            rows: peBand.map((p, i) => [p.date, p.pe, pbBand[i]?.pb ?? null]),
          }}
        />
      ) : (
        <p className="text-sm text-muted">Not enough price/EPS/BVPS history for a P/E-P/B band.</p>
      )}

      {valuation.dcf_applicable ? (
        <div className="rounded-lg border border-border bg-surface p-4">
          <h3 className="mb-3 text-sm font-medium">DCF calculator (FCFF, 2-stage Gordon growth)</h3>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div className="space-y-3">
              <Slider
                label="FCFF growth (yrs 1-5)"
                value={growthPct ?? valuation.dcf_inputs.growth_rate_pct ?? 5}
                onChange={setGrowthPct}
                min={-10}
                max={30}
                step={0.5}
                suffix="%"
              />
              <Slider label="WACC" value={waccPct} onChange={setWaccPct} min={6} max={20} step={0.5} suffix="%" />
              <Slider
                label="Terminal growth"
                value={terminalGrowthPct}
                onChange={setTerminalGrowthPct}
                min={0}
                max={8}
                step={0.5}
                suffix="%"
              />
              <p className="text-xs text-muted">
                Base FCFF: {formatRupees(valuation.dcf_inputs.base_fcff)} Cr. Note: this calculator projects FCFF
                directly at the growth rate above (not decomposed via a separate revenue/EBITDA-margin build-up).
              </p>
            </div>
            <div className="space-y-2 rounded-md border border-border p-3">
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted">Intrinsic value/share</span>
                <span className="font-semibold tabular-nums-fixed">{formatRupees(intrinsic)}</span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted">LTP</span>
                <span className="tabular-nums-fixed">{formatRupees(ltp)}</span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted">Upside/(downside)</span>
                <span className={upsidePct != null && upsidePct < 0 ? "text-down" : "text-up"}>
                  {upsidePct != null ? `${upsidePct >= 0 ? "+" : ""}${upsidePct.toFixed(1)}%` : MISSING_VALUE_PLACEHOLDER}
                </span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted">Reverse DCF implied growth</span>
                <span className="tabular-nums-fixed">{formatPercent(valuation.reverse_dcf_implied_growth_pct)}</span>
              </div>
            </div>
          </div>

          {valuation.sensitivity_table && (
            <div className="mt-4 overflow-x-auto">
              <p className="mb-1 text-xs text-muted">Sensitivity: intrinsic value/share (WACC rows x terminal growth columns)</p>
              <table className="text-xs">
                <thead>
                  <tr>
                    <th className="border border-border px-2 py-1">WACC \ g</th>
                    {valuation.sensitivity_table.terminal_growth_values_pct.map((t) => (
                      <th key={t} className="border border-border px-2 py-1">{t.toFixed(1)}%</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {valuation.sensitivity_table.wacc_values_pct.map((w, ri) => (
                    <tr key={w}>
                      <td className="border border-border px-2 py-1 font-medium">{w.toFixed(1)}%</td>
                      {valuation.sensitivity_table!.values[ri].map((v, ci) => (
                        <td key={ci} className="border border-border px-2 py-1 text-right tabular-nums-fixed">
                          {formatRupees(v, 0)}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      ) : (
        <div className="rounded-lg border border-amber-500/40 bg-amber-500/10 p-3 text-sm">
          DCF not applicable for a {template} template -- use P/B vs ROE instead.
        </div>
      )}

      {isFinancial &&
        (pbRoeScatter ? (
          <ChartCard title="P/B vs ROE, template peers" option={pbRoeScatter} height={280} />
        ) : (
          <p className="text-sm text-muted">Not enough peer data for a P/B vs ROE scatter.</p>
        ))}
    </div>
  );
}
