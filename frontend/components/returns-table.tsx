"use client";

import { useQueries } from "@tanstack/react-query";
import { useHistory, usePeers } from "@/lib/queries";
import { api } from "@/lib/api";
import { computeReturnsTable, RETURN_SPANS } from "@/lib/technical";
import { formatPercent, changeDirection } from "@/lib/format";
import { cn } from "@/lib/utils";

const PEER_HISTORY_CAP = 10;

function SignedCell({ value, cagrPct }: { value: number | null; cagrPct?: number | null }) {
  const direction = changeDirection(value);
  return (
    <div>
      <span
        className={cn(
          "tabular-nums-fixed",
          direction === "up" && "text-up",
          direction === "down" && "text-down",
          direction === "flat" && "text-muted"
        )}
      >
        {formatPercent(value, 1)}
      </span>
      {cagrPct != null && <div className="text-[10px] text-muted">CAGR {formatPercent(cagrPct, 1)}</div>}
    </div>
  );
}

export function ReturnsTable({ symbol }: { symbol: string }) {
  const { data: history, isLoading } = useHistory(symbol, "5y", "1d");
  const { data: peers } = usePeers(symbol);

  const peerSymbols = (peers?.peers ?? [])
    .map((p) => p.symbol)
    .filter((s) => s !== symbol)
    .slice(0, PEER_HISTORY_CAP);

  // Shares its cache/query key shape with `useHistory` (["history", symbol,
  // range, interval]) -- a peer whose own Overview tab is also open in
  // this session dedupes against that query instead of double-fetching.
  const peerHistoryQueries = useQueries({
    queries: peerSymbols.map((s) => ({
      queryKey: ["history", s, "5y", "1d"],
      queryFn: () => api.history(s, "5y", "1d"),
      staleTime: 6 * 60 * 60 * 1000,
    })),
  });

  if (isLoading || !history) {
    return <div className="h-24 animate-pulse rounded-lg border border-border bg-surface" />;
  }

  const bars = history.bars.map((b) => ({ date: b.date.slice(0, 10), close: b.close ?? null }));
  const stockRows = computeReturnsTable(bars);

  const benchmarkBars = (history.benchmark_bars ?? []).map((b) => ({
    date: b.date.slice(0, 10),
    close: b.close ?? null,
  }));
  const niftyRows = computeReturnsTable(benchmarkBars);

  // Sector/template peer average return per span (same "average across the
  // peer group" pattern already used for the median in peer-strip-chart.tsx)
  // -- a real per-sector NSE index isn't part of this app's data model, so
  // an equal-weighted average of the peer group's own returns stands in
  // for it, same peer group the Peers/Ratios tabs already use.
  const peerReturnsPerSpan = peerHistoryQueries
    .filter((q) => q.data)
    .map((q) => {
      const peerBars = (q.data!.bars ?? []).map((b) => ({ date: b.date.slice(0, 10), close: b.close ?? null }));
      return computeReturnsTable(peerBars);
    });
  const sectorRows = RETURN_SPANS.map((span, i) => {
    const values = peerReturnsPerSpan.map((rows) => rows[i]?.returnPct).filter((v): v is number => v !== null);
    return values.length > 0 ? values.reduce((a, b) => a + b, 0) / values.length : null;
  });

  return (
    <div className="rounded-lg border border-border bg-surface p-4">
      <h3 className="mb-3 text-sm font-medium">Returns</h3>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border text-left text-xs text-muted">
              <th className="py-1.5 pr-4 font-normal">Period</th>
              {stockRows.map((row) => (
                <th key={row.label} className="px-2 py-1.5 text-center font-normal">
                  {row.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {(
              [
                {
                  label: symbol,
                  rows: stockRows.map((r) => r.returnPct),
                  cagr: stockRows.map((r) => r.cagrPct),
                },
                { label: "NIFTY 50", rows: niftyRows.map((r) => r.returnPct) },
                { label: "Sector avg", rows: sectorRows },
                {
                  label: "Alpha (vs NIFTY)",
                  rows: stockRows.map((r, i) =>
                    r.returnPct !== null && niftyRows[i]?.returnPct !== null
                      ? r.returnPct - (niftyRows[i].returnPct as number)
                      : null
                  ),
                },
              ] as const
            ).map((line) => (
              <tr key={line.label} className="border-b border-border/50 last:border-0">
                <td className="py-1.5 pr-4 text-xs text-muted">{line.label}</td>
                {line.rows.map((value, i) => (
                  <td key={i} className="px-2 py-1.5 text-center">
                    <SignedCell value={value} cagrPct={"cagr" in line ? line.cagr[i] : null} />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
