"use client";

import { useMemo } from "react";
import { useUniverse, useQuotes } from "@/lib/queries";
import { useSelection } from "@/hooks/use-selection";
import { changeDirection, changeGlyph, formatPercent, formatRupees } from "@/lib/format";
import { cn } from "@/lib/utils";

export function TickerTape() {
  const { data: universe } = useUniverse();
  const { selectSymbolAnySector } = useSelection();

  const allSymbols = useMemo(
    () => universe?.sectors.flatMap((s) => s.companies.map((c) => c.symbol)) ?? [],
    [universe]
  );
  const { data: quotes } = useQuotes(allSymbols);

  if (!quotes || quotes.length === 0) {
    return <div className="h-9 border-y border-border" aria-hidden />;
  }

  // Duplicate the list so the CSS scroll animation loops seamlessly.
  const items = [...quotes, ...quotes];

  return (
    <div className="group relative overflow-hidden border-y border-border bg-surface">
      <div className="flex w-max animate-[ticker-scroll_60s_linear_infinite] group-hover:[animation-play-state:paused]">
        {items.map((quote, i) => {
          const direction = changeDirection(quote.change_pct);
          return (
            <button
              key={`${quote.symbol}-${i}`}
              onClick={() => selectSymbolAnySector(quote.symbol)}
              className="flex shrink-0 items-center gap-1.5 px-4 py-2 text-xs hover:bg-surface-raised"
            >
              <span className="font-medium">{quote.symbol}</span>
              <span className="tabular-nums-fixed">{formatRupees(quote.last_price)}</span>
              <span
                className={cn(
                  "tabular-nums-fixed",
                  direction === "up" && "text-up",
                  direction === "down" && "text-down",
                  direction === "flat" && "text-muted"
                )}
              >
                {changeGlyph(quote.change_pct)} {formatPercent(quote.change_pct)}
              </span>
            </button>
          );
        })}
      </div>
      <style jsx>{`
        @keyframes ticker-scroll {
          from {
            transform: translateX(0);
          }
          to {
            transform: translateX(-50%);
          }
        }
      `}</style>
    </div>
  );
}
