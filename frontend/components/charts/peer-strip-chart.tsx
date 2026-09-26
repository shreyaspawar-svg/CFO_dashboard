"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import type { EChartsOption } from "echarts";
import { useTheme } from "next-themes";
import { ChartCard } from "@/components/charts/chart-card";
import { chartThemeFor } from "@/lib/chart-theme";
import { usePeers, useUniverse } from "@/lib/queries";
import { ratioGroupsFor } from "@/lib/ratio-groups";
import { formatIndianNumber } from "@/lib/format";

/** A dot for every sector/template peer on one axis, the selected company
 * highlighted, a median line, and clicking a dot navigates to that company
 * (PLAN.md §4.3 item 5). */
export function PeerStripChart({ symbol, template }: { symbol: string; template: string }) {
  const { data: peers } = usePeers(symbol);
  const { data: universe } = useUniverse();
  const { resolvedTheme } = useTheme();
  const theme = chartThemeFor(resolvedTheme);
  const router = useRouter();

  const availableRatios = useMemo(
    () => ratioGroupsFor(template).flatMap((g) => g.ratios).filter((r) => r.available),
    [template]
  );
  const [ratioKey, setRatioKey] = useState<string>(availableRatios[0]?.key ?? "roe");

  const points = useMemo(() => {
    if (!peers) return [];
    return peers.peers
      .map((p) => ({ symbol: p.symbol, name: p.name, value: p.metrics[ratioKey] ?? null }))
      .filter((p): p is { symbol: string; name: string; value: number } => p.value !== null);
  }, [peers, ratioKey]);

  const median = useMemo(() => {
    if (points.length === 0) return null;
    const sorted = [...points.map((p) => p.value)].sort((a, b) => a - b);
    return sorted[Math.floor(sorted.length / 2)];
  }, [points]);

  // Deterministic per-symbol vertical jitter (not Math.random(), which
  // would re-jitter on every render and mismatch between server/client
  // renders) -- purely a visual de-overlap for same/close values.
  const jitterFor = (s: string): number => {
    let hash = 0;
    for (let i = 0; i < s.length; i++) hash = (hash * 31 + s.charCodeAt(i)) % 1000;
    return (hash / 1000 - 0.5) * 0.6;
  };

  const navigateToSymbol = (targetSymbol: string) => {
    if (!universe) return;
    const sector = universe.sectors.find((s) => s.companies.some((c) => c.symbol === targetSymbol));
    if (!sector) return;
    const params = new URLSearchParams({ sector: sector.name, symbol: targetSymbol });
    router.push(`/?${params.toString()}`, { scroll: false });
  };

  const option = useMemo<EChartsOption | null>(() => {
    if (points.length === 0) return null;
    // ECharts' own callback param types (CallbackDataParams) are awkward
    // to satisfy precisely for a scatter series carrying a 3rd, non-numeric
    // data dimension (the peer's symbol, for the click handler and the
    // "highlight the selected company" styling) -- typed loosely here and
    // cast at the boundary rather than fighting the library's generics.
    const rowIsSelected = (data: unknown): boolean => Array.isArray(data) && data[2] === symbol;
    const series: Record<string, unknown>[] = [
      {
        type: "scatter",
        symbolSize: (val: unknown) => (Array.isArray(val) && val[2] === symbol ? 16 : 10),
        data: points.map((p) => [p.value, jitterFor(p.symbol), p.symbol]),
        itemStyle: {
          color: (params: { data: unknown }) => (rowIsSelected(params.data) ? theme.accent : theme.muted),
        },
        label: {
          show: true,
          formatter: (params: { data: unknown }) =>
            rowIsSelected(params.data) ? String((params.data as unknown[])[2]) : "",
          position: "top",
          color: theme.foreground,
          fontWeight: "bold",
        },
        markLine: median
          ? {
              symbol: "none",
              silent: true,
              lineStyle: { color: theme.border, type: "dashed" },
              label: { formatter: "Median", color: theme.muted },
              data: [{ xAxis: median }],
            }
          : undefined,
      },
    ];
    return {
      grid: { left: 16, right: 16, top: 32, bottom: 40 },
      xAxis: {
        type: "value",
        axisLabel: { color: theme.muted, formatter: (v: number) => formatIndianNumber(v, 1) },
        splitLine: { lineStyle: { color: theme.border } },
      },
      yAxis: { type: "value", show: false, min: -1, max: 1 },
      series,
    } as EChartsOption;
  }, [points, median, theme, symbol]);

  return (
    <div className="rounded-lg border border-border bg-surface p-4">
      <div className="mb-2 flex items-center justify-between">
        <h3 className="text-sm font-medium">Peer comparison</h3>
        <select
          value={ratioKey}
          onChange={(e) => setRatioKey(e.target.value)}
          className="rounded-md border border-border bg-background px-2 py-1 text-xs"
        >
          {availableRatios.map((r) => (
            <option key={r.key} value={r.key}>
              {r.label}
            </option>
          ))}
        </select>
      </div>
      {option ? (
        <ChartCard
          title=""
          option={option}
          height={180}
          csv={{
            filename: `${symbol}_peers_${ratioKey}.csv`,
            headers: ["Symbol", "Name", "Value"],
            rows: points.map((p) => [p.symbol, p.name, p.value]),
          }}
          onEvents={{
            click: (params: unknown) => {
              const data = (params as { data?: unknown[] }).data;
              const clickedSymbol = data?.[2];
              if (typeof clickedSymbol === "string") navigateToSymbol(clickedSymbol);
            },
          }}
        />
      ) : (
        <p className="text-sm text-muted">No peer data for this ratio.</p>
      )}
      <p className="mt-2 text-xs text-muted">Click a peer&apos;s dot to open it. Highlighted dot is {symbol}.</p>
      {points.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {points.map((p) => (
            <button
              key={p.symbol}
              onClick={() => navigateToSymbol(p.symbol)}
              className={
                p.symbol === symbol
                  ? "rounded-full bg-accent px-2 py-0.5 text-xs text-white"
                  : "rounded-full border border-border px-2 py-0.5 text-xs text-muted hover:text-foreground"
              }
            >
              {p.symbol}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
