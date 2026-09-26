"use client";

import { useHistory } from "@/lib/queries";
import { computeReturnsTable } from "@/lib/technical";
import { formatPercent, changeDirection } from "@/lib/format";
import { cn } from "@/lib/utils";

export function ReturnsTable({ symbol }: { symbol: string }) {
  const { data: history, isLoading } = useHistory(symbol, "5y", "1d");

  if (isLoading || !history) {
    return <div className="h-24 animate-pulse rounded-lg border border-border bg-surface" />;
  }

  const bars = history.bars.map((b) => ({ date: b.date.slice(0, 10), close: b.close ?? null }));
  const rows = computeReturnsTable(bars);

  return (
    <div className="rounded-lg border border-border bg-surface p-4">
      <h3 className="mb-3 text-sm font-medium">Returns</h3>
      <div className="grid grid-cols-3 gap-3 sm:grid-cols-6">
        {rows.map((row) => {
          const direction = changeDirection(row.returnPct);
          return (
            <div key={row.label} className="text-center">
              <div className="text-xs text-muted">{row.label}</div>
              <div
                className={cn(
                  "tabular-nums-fixed text-sm font-medium",
                  direction === "up" && "text-up",
                  direction === "down" && "text-down",
                  direction === "flat" && "text-muted"
                )}
              >
                {formatPercent(row.returnPct, 1)}
              </div>
              {row.cagrPct !== null && (
                <div className="text-[10px] text-muted">CAGR {formatPercent(row.cagrPct, 1)}</div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
