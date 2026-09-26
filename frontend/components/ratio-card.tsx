"use client";

import { useState } from "react";
import { AlertTriangle, Info } from "lucide-react";
import {
  formatCrore,
  formatIndianNumber,
  formatMultiple,
  formatPercent,
  NOT_MEANINGFUL_PLACEHOLDER,
  type Unit,
} from "@/lib/format";
import type { KpiDef } from "@/lib/kpi-templates";
import type { GlossaryEntry, RatioHistoryPoint, RatioValue } from "@/lib/api";
import { RatioSparkline } from "@/components/ratio-sparkline";

function formatterFor(format: KpiDef["format"], unit: Unit) {
  switch (format) {
    case "percent":
      return (v: number | null | undefined) => formatPercent(v);
    case "multiple":
      return (v: number | null | undefined) => formatMultiple(v);
    case "crore":
      return (v: number | null | undefined) => formatCrore(v, unit);
    case "days":
      return (v: number | null | undefined) => (v == null ? "—" : `${formatIndianNumber(v, 0)}d`);
  }
}

function percentileLabel(percentile: number): string {
  if (percentile >= 90) return "Top 10%";
  if (percentile >= 75) return "Top 25%";
  if (percentile >= 50) return "Above median";
  if (percentile >= 25) return "Below median";
  return "Bottom 25%";
}

export function RatioCard({
  def,
  ratio,
  history,
  comparableFrom,
  glossary,
  peerBasis,
  peerCount,
  unit,
}: {
  def: KpiDef;
  ratio: RatioValue | undefined;
  history: RatioHistoryPoint[];
  comparableFrom: string | null;
  glossary: GlossaryEntry | undefined;
  peerBasis: "sector" | "template" | "none";
  peerCount: number;
  unit: Unit;
}) {
  const [showGlossary, setShowGlossary] = useState(false);
  const format = formatterFor(def.format, unit);
  const isInconsistent = ratio?.data_quality === "inconsistent";
  const isNotMeaningful = ratio?.value == null && ratio?.reason === "not_meaningful";

  // PLAN.md §4.3 item 2: no percentile badge with fewer than 3 peers.
  const showPercentile = peerCount >= 3 && ratio?.percentile != null;

  let rangePct: number | null = null;
  let medianPct: number | null = null;
  if (ratio?.value != null && ratio.peer_min != null && ratio.peer_max != null && ratio.peer_max > ratio.peer_min) {
    const span = ratio.peer_max - ratio.peer_min;
    rangePct = Math.max(0, Math.min(100, ((ratio.value - ratio.peer_min) / span) * 100));
    if (ratio.peer_median != null) {
      medianPct = Math.max(0, Math.min(100, ((ratio.peer_median - ratio.peer_min) / span) * 100));
    }
  }

  return (
    <div className="rounded-lg border border-border bg-surface p-3">
      <div className="flex items-start justify-between gap-1">
        <div className="flex items-center gap-1 text-xs text-muted">
          <span>{def.label}</span>
          {glossary && (
            <button
              type="button"
              onClick={() => setShowGlossary((v) => !v)}
              className="inline-flex shrink-0 items-center text-muted hover:text-foreground"
              aria-label={`About ${def.label}`}
              title={`${glossary.formula} -- ${glossary.meaning}`}
            >
              <Info size={12} />
            </button>
          )}
          {isInconsistent && (
            <span
              className="inline-flex shrink-0 items-center text-amber-500"
              title={ratio?.data_quality_reason ?? "Source data inconsistent"}
              aria-label="Source data inconsistent"
            >
              <AlertTriangle size={12} />
            </span>
          )}
        </div>
        {!def.available ? null : <RatioSparkline points={history} comparableFrom={comparableFrom} />}
      </div>

      {!def.available ? (
        <div className="mt-1 text-sm text-muted" title="Not in free data source">
          —
        </div>
      ) : isNotMeaningful ? (
        <div className="mt-1 text-lg font-semibold tabular-nums-fixed text-muted" title="Not meaningful: prior-period value ≤ 0">
          {NOT_MEANINGFUL_PLACEHOLDER}
        </div>
      ) : (
        <>
          <div className="mt-1 text-lg font-semibold tabular-nums-fixed">{format(ratio?.value)}</div>
          {rangePct !== null && (
            <div className="relative mt-1.5 h-1 rounded-full bg-border" title={`Sector range: ${format(ratio?.peer_min)} - ${format(ratio?.peer_max)}`}>
              {medianPct !== null && (
                <div
                  className="absolute top-1/2 h-2 w-px -translate-y-1/2 bg-muted"
                  style={{ left: `${medianPct}%` }}
                />
              )}
              <div
                className="absolute top-1/2 h-2 w-2 -translate-x-1/2 -translate-y-1/2 rounded-full bg-accent"
                style={{ left: `${rangePct}%` }}
              />
            </div>
          )}
          <div className="mt-1 flex items-center justify-between text-xs text-muted tabular-nums-fixed">
            <span>{ratio?.peer_median != null ? `Median: ${format(ratio.peer_median)}` : ""}</span>
            {showPercentile && ratio?.percentile != null && (
              <span>
                {percentileLabel(ratio.percentile)} {peerBasis === "template" ? "vs template" : "in sector"}
              </span>
            )}
          </div>
        </>
      )}

      {showGlossary && glossary && (
        <div className="mt-2 rounded-md bg-background/60 p-2 text-xs text-muted">
          <p className="font-medium text-foreground">{glossary.formula}</p>
          <p className="mt-1">{glossary.meaning}</p>
          <p className="mt-1 italic">{glossary.good_looks_like}</p>
        </div>
      )}
    </div>
  );
}
