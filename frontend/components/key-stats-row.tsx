"use client";

import { useOverview, useQuote } from "@/lib/queries";
import { formatCrore, formatMultiple, formatRupees } from "@/lib/format";
import { useSelectionStore } from "@/lib/store";

export function KeyStatsRow({ symbol }: { symbol: string }) {
  const { data: overview, isLoading } = useOverview(symbol);
  const { data: quote } = useQuote(symbol);
  const unit = useSelectionStore((s) => s.unit);

  if (isLoading || !overview) {
    return <div className="h-20 animate-pulse rounded-lg border border-border bg-surface" />;
  }

  const stats: { label: string; value: string }[] = [
    { label: "Beta (1Y vs NIFTY 50)", value: overview.beta !== null ? formatMultiple(overview.beta) : "—" },
    { label: "Market cap", value: formatCrore(quote?.market_cap, unit) },
    {
      label: "Analyst target (mean)",
      value: overview.analyst_target_mean !== null ? formatRupees(overview.analyst_target_mean) : "—",
    },
    {
      label: "Analyst range",
      value:
        overview.analyst_target_low !== null && overview.analyst_target_high !== null
          ? `${formatRupees(overview.analyst_target_low, 0)} – ${formatRupees(overview.analyst_target_high, 0)}`
          : "—",
    },
    {
      label: "Analyst recommendation",
      value: overview.analyst_recommendation
        ? overview.analyst_recommendation.replace(/_/g, " ")
        : "—",
    },
    {
      label: "Coverage",
      value: overview.analyst_count !== null ? `${overview.analyst_count} analysts` : "—",
    },
  ];

  return (
    <div className="rounded-lg border border-border bg-surface p-4">
      <h3 className="mb-3 text-sm font-medium">Key stats</h3>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        {stats.map((stat) => (
          <div key={stat.label}>
            <div className="text-xs text-muted">{stat.label}</div>
            <div className="tabular-nums-fixed text-sm font-medium capitalize">{stat.value}</div>
          </div>
        ))}
      </div>
      {(overview.warnings ?? []).length > 0 && (
        <p className="mt-3 text-xs text-muted">
          {(overview.warnings ?? []).filter((w) => w.includes("unavailable")).join(" · ")}
        </p>
      )}
    </div>
  );
}
