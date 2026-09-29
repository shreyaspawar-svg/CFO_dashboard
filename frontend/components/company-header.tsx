"use client";

import { useEffect, useState } from "react";
import { AlertTriangle } from "lucide-react";
import { useQuote, useFinancials } from "@/lib/queries";
import { CompanyAvatar } from "@/components/company-combobox";
import { RangeBar } from "@/components/range-bar";
import { WarningBanner } from "@/components/warning-banner";
import { CompanyHeaderSkeleton } from "@/components/skeletons";
import { useFlashOnChange } from "@/hooks/use-flash-on-change";
import { changeDirection, changeGlyph, formatCrore, formatPercent, formatRupees } from "@/lib/format";
import { useSelectionStore } from "@/lib/store";
import { cn } from "@/lib/utils";
import type { CompanyRef } from "@/lib/api";

const STALE_AFTER_MS = 5 * 60 * 1000;

export function CompanyHeader({ company, sectorName }: { company: CompanyRef; sectorName: string }) {
  const { data: quote, isLoading } = useQuote(company.symbol);
  const { data: financials } = useFinancials(company.symbol, "annual");
  const unit = useSelectionStore((s) => s.unit);
  const flash = useFlashOnChange(quote?.last_price);

  // Re-checked every 30s (PLAN.md Phase 5 §B.4) so the badge can appear
  // between polls, not just when a new quote happens to arrive.
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 30_000);
    return () => clearInterval(id);
  }, []);

  if (isLoading || !quote) return <CompanyHeaderSkeleton />;

  const direction = changeDirection(quote.change_pct);
  const ageMs = now - new Date(quote.as_of).getTime();
  const isStale = quote.stale || (quote.market_status === "open" && ageMs > STALE_AFTER_MS);

  return (
    <div className="space-y-3">
      {financials?.notes && financials.notes.length > 0 && <WarningBanner notes={financials.notes} />}

      <div className="space-y-3 rounded-lg border border-border bg-surface p-4">
        <div className="flex flex-wrap items-start gap-4">
          <div className="flex items-center gap-3">
            <CompanyAvatar name={company.name} />
            <div>
              <div className="font-semibold">{company.name}</div>
              <div className="text-xs text-muted">
                {company.symbol} &middot; {sectorName}
              </div>
            </div>
          </div>

          <div className="ml-auto text-right">
            {isStale && (
              <div
                className="mb-1 inline-flex items-center gap-1 rounded-full border border-amber-500/40 bg-amber-500/10 px-2 py-0.5 text-xs text-amber-500"
                title={quote.stale ? "Live fetch failed; showing the last known quote" : "Quote is more than 5 minutes old"}
              >
                <AlertTriangle size={12} /> Stale
              </div>
            )}
            <div
              className={cn(
                "hero-number inline-block rounded px-1.5 tabular-nums-fixed text-xl font-semibold transition-colors",
                flash === "up" && "price-flash-up",
                flash === "down" && "price-flash-down"
              )}
            >
              {formatRupees(quote.last_price)}
            </div>
            <div
              className={cn(
                "text-sm tabular-nums-fixed",
                direction === "up" && "text-up",
                direction === "down" && "text-down",
                direction === "flat" && "text-muted"
              )}
            >
              {changeGlyph(quote.change_pct)} {formatRupees(quote.change)} ({formatPercent(quote.change_pct)})
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <RangeBar low={quote.day_low} high={quote.day_high} current={quote.last_price} label="Day range" />
          <RangeBar
            low={quote.week52_low}
            high={quote.week52_high}
            current={quote.last_price}
            label="52-week range"
          />
        </div>

        <div className="flex flex-wrap gap-6 text-sm">
          <div>
            <div className="text-xs text-muted">Market cap</div>
            <div className="tabular-nums-fixed">{formatCrore(quote.market_cap, unit)}</div>
          </div>
          <div>
            <div className="text-xs text-muted">Volume</div>
            <div className="tabular-nums-fixed">
              {quote.volume ? new Intl.NumberFormat("en-IN").format(quote.volume) : "—"}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
