"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import type { EChartsOption } from "echarts";
import { useTheme } from "next-themes";
import { Download } from "lucide-react";
import { usePeers, useUniverse } from "@/lib/queries";
import { ChartCard } from "@/components/charts/chart-card";
import { chartThemeFor } from "@/lib/chart-theme";
import { downloadCsv } from "@/lib/chart-export";
import { formatIndianNumber, formatMultiple, formatPercent, formatRupees, MISSING_VALUE_PLACEHOLDER } from "@/lib/format";
import { Button } from "@/components/ui/button";

const TEMPLATE_COLUMNS: Record<string, { key: string; label: string; fmt: (v: number | null) => string }[]> = {
  general: [
    { key: "pe", label: "P/E", fmt: formatMultiple },
    { key: "pb", label: "P/B", fmt: formatMultiple },
    { key: "ev_ebitda", label: "EV/EBITDA", fmt: formatMultiple },
    { key: "roe", label: "ROE", fmt: formatPercent },
    { key: "roce", label: "ROCE", fmt: formatPercent },
    { key: "revenue_cagr_3y", label: "Rev 3Y CAGR", fmt: formatPercent },
    { key: "pat_margin", label: "PAT margin", fmt: formatPercent },
    { key: "debt_to_equity", label: "D/E", fmt: formatMultiple },
  ],
};
TEMPLATE_COLUMNS.exchange = TEMPLATE_COLUMNS.general;
TEMPLATE_COLUMNS.bank = [
  { key: "pe", label: "P/E", fmt: formatMultiple },
  { key: "pb", label: "P/B", fmt: formatMultiple },
  { key: "roe", label: "ROE", fmt: formatPercent },
  { key: "roa", label: "ROA", fmt: formatPercent },
  { key: "nim", label: "NIM", fmt: formatPercent },
  { key: "revenue_cagr_3y", label: "Rev 3Y CAGR", fmt: formatPercent },
];
TEMPLATE_COLUMNS.nbfc = TEMPLATE_COLUMNS.bank;
TEMPLATE_COLUMNS.insurance = [
  { key: "pe", label: "P/E", fmt: formatMultiple },
  { key: "pb", label: "P/B", fmt: formatMultiple },
  { key: "roe", label: "ROE", fmt: formatPercent },
  { key: "revenue_cagr_3y", label: "Rev 3Y CAGR", fmt: formatPercent },
];

export function PeersTab({ symbol, template }: { symbol: string; template: string }) {
  const { data: peers, isLoading } = usePeers(symbol);
  const { data: universe } = useUniverse();
  const { resolvedTheme } = useTheme();
  const theme = chartThemeFor(resolvedTheme);
  const router = useRouter();

  const columns = TEMPLATE_COLUMNS[template] ?? TEMPLATE_COLUMNS.general;
  const [sortKey, setSortKey] = useState<string>("market_cap");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [xKey, setXKey] = useState(columns[2]?.key ?? "roe");
  const [yKey, setYKey] = useState(columns[0]?.key ?? "pe");
  const [rankKey, setRankKey] = useState(columns[0]?.key ?? "pe");

  const navigateToSymbol = (targetSymbol: string) => {
    if (!universe) return;
    const sector = universe.sectors.find((s) => s.companies.some((c) => c.symbol === targetSymbol));
    if (!sector) return;
    router.push(`/?${new URLSearchParams({ sector: sector.name, symbol: targetSymbol }).toString()}`, {
      scroll: false,
    });
  };

  const rows = useMemo(() => {
    if (!peers) return [];
    const withValues = peers.peers.map((p) => ({
      ...p,
      sortValue: sortKey === "market_cap" ? p.market_cap : sortKey === "last_price" ? p.last_price : p.metrics[sortKey],
    }));
    return [...withValues].sort((a, b) => {
      const av = a.sortValue ?? -Infinity;
      const bv = b.sortValue ?? -Infinity;
      return sortDir === "asc" ? av - bv : bv - av;
    });
  }, [peers, sortKey, sortDir]);

  const toggleSort = (key: string) => {
    if (sortKey === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir("desc");
    }
  };

  const scatterOption = useMemo<EChartsOption | null>(() => {
    if (!peers) return null;
    const points = peers.peers
      .map((p) => ({
        symbol: p.symbol,
        x: p.metrics[xKey],
        y: p.metrics[yKey],
        size: p.market_cap,
      }))
      .filter((p): p is { symbol: string; x: number; y: number; size: number } => p.x != null && p.y != null && p.size != null);
    if (points.length === 0) return null;
    const maxSize = Math.max(...points.map((p) => p.size));
    return {
      grid: { left: 56, right: 16, top: 24, bottom: 40 },
      xAxis: { type: "value", name: xKey, axisLabel: { color: theme.muted } },
      yAxis: { type: "value", name: yKey, axisLabel: { color: theme.muted } },
      series: [
        {
          type: "scatter",
          data: points.map((p) => [p.x, p.y, p.symbol, p.size]),
          symbolSize: (val: unknown) => (Array.isArray(val) ? 10 + (Number(val[3]) / maxSize) * 30 : 10),
          itemStyle: {
            color: (params: { data: unknown }) =>
              Array.isArray(params.data) && params.data[2] === symbol ? theme.accent : theme.muted,
            opacity: 0.75,
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
  }, [peers, xKey, yKey, theme, symbol]);

  const rankOption = useMemo<EChartsOption | null>(() => {
    if (!peers) return null;
    const points = peers.peers
      .map((p) => ({ symbol: p.symbol, value: p.metrics[rankKey] }))
      .filter((p): p is { symbol: string; value: number } => p.value != null)
      .sort((a, b) => b.value - a.value);
    if (points.length === 0) return null;
    return {
      grid: { left: 80, right: 24, top: 16, bottom: 24 },
      xAxis: { type: "value", axisLabel: { color: theme.muted } },
      yAxis: { type: "category", data: points.map((p) => p.symbol).reverse(), axisLabel: { color: theme.muted } },
      series: [
        {
          type: "bar",
          data: points
            .map((p) => p.value)
            .reverse()
            .map((v, i, arr) => ({
              value: v,
              itemStyle: { color: points[arr.length - 1 - i].symbol === symbol ? theme.accent : theme.muted },
            })),
        },
      ],
    } as EChartsOption;
  }, [peers, rankKey, theme, symbol]);

  if (isLoading || !peers) {
    return <div className="h-80 animate-pulse rounded-lg border border-border bg-surface" />;
  }

  const validValues = (key: string) => peers.peers.map((p) => p.metrics[key]).filter((v): v is number => v != null);
  const columnMedian = (key: string) => (peers.peer_medians ?? {})[key] ?? null;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-xs text-muted">Peer basis: {peers.peer_basis} · {peers.peers.length} companies</p>
        <Button
          variant="outline"
          size="sm"
          onClick={() =>
            downloadCsv(
              `${symbol}_peers.csv`,
              ["Symbol", "Name", "LTP", "Mkt cap (Cr)", ...columns.map((c) => c.label)],
              rows.map((r) => [r.symbol, r.name, r.last_price, r.market_cap, ...columns.map((c) => r.metrics[c.key])])
            )
          }
        >
          <Download size={14} className="mr-1" /> CSV
        </Button>
      </div>

      <div className="overflow-x-auto rounded-lg border border-border bg-surface">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border text-left text-xs text-muted">
              <th className="cursor-pointer py-2 pl-3 pr-4 font-normal" onClick={() => toggleSort("symbol")}>
                Company
              </th>
              <th className="cursor-pointer px-2 py-2 text-right font-normal" onClick={() => toggleSort("last_price")}>
                LTP
              </th>
              <th className="cursor-pointer px-2 py-2 text-right font-normal" onClick={() => toggleSort("market_cap")}>
                Mkt cap (Cr)
              </th>
              {columns.map((c) => (
                <th
                  key={c.key}
                  className="cursor-pointer px-2 py-2 text-right font-normal"
                  onClick={() => toggleSort(c.key)}
                >
                  {c.label}
                  {sortKey === c.key ? (sortDir === "asc" ? " ▲" : " ▼") : ""}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr
                key={r.symbol}
                onClick={() => navigateToSymbol(r.symbol)}
                className={`cursor-pointer border-b border-border/50 hover:bg-background ${
                  r.symbol === symbol ? "bg-accent/10 font-medium" : ""
                }`}
              >
                <td className="py-1.5 pl-3 pr-4">
                  {r.symbol} <span className="text-xs text-muted">{r.name}</span>
                </td>
                <td className="px-2 py-1.5 text-right tabular-nums-fixed">{formatRupees(r.last_price)}</td>
                <td className="px-2 py-1.5 text-right tabular-nums-fixed">{formatIndianNumber(r.market_cap, 0)}</td>
                {columns.map((c) => (
                  <td key={c.key} className="px-2 py-1.5 text-right tabular-nums-fixed">
                    {c.fmt(r.metrics[c.key] ?? null)}
                  </td>
                ))}
              </tr>
            ))}
            <tr className="border-t-2 border-border bg-background/60 text-xs">
              <td className="py-1.5 pl-3 pr-4 font-medium">Median</td>
              <td className="px-2 py-1.5 text-right" />
              <td className="px-2 py-1.5 text-right" />
              {columns.map((c) => (
                <td key={c.key} className="px-2 py-1.5 text-right tabular-nums-fixed">
                  {validValues(c.key).length > 0 ? c.fmt(columnMedian(c.key)) : MISSING_VALUE_PLACEHOLDER}
                </td>
              ))}
            </tr>
          </tbody>
        </table>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div>
          <div className="mb-2 flex items-center gap-2 text-xs">
            <span className="text-muted">X</span>
            <select value={xKey} onChange={(e) => setXKey(e.target.value)} className="rounded-md border border-border bg-background px-2 py-1">
              {columns.map((c) => (
                <option key={c.key} value={c.key}>{c.label}</option>
              ))}
            </select>
            <span className="text-muted">Y</span>
            <select value={yKey} onChange={(e) => setYKey(e.target.value)} className="rounded-md border border-border bg-background px-2 py-1">
              {columns.map((c) => (
                <option key={c.key} value={c.key}>{c.label}</option>
              ))}
            </select>
          </div>
          {scatterOption ? (
            <ChartCard title="Bubble scatter (bubble size = mkt cap)" option={scatterOption} height={320} />
          ) : (
            <p className="text-sm text-muted">Not enough data for this pair.</p>
          )}
        </div>
        <div>
          <div className="mb-2 flex items-center gap-2 text-xs">
            <span className="text-muted">Rank by</span>
            <select value={rankKey} onChange={(e) => setRankKey(e.target.value)} className="rounded-md border border-border bg-background px-2 py-1">
              {columns.map((c) => (
                <option key={c.key} value={c.key}>{c.label}</option>
              ))}
            </select>
          </div>
          {rankOption ? (
            <ChartCard title="Rank" option={rankOption} height={320} />
          ) : (
            <p className="text-sm text-muted">Not enough data to rank.</p>
          )}
        </div>
      </div>
    </div>
  );
}
