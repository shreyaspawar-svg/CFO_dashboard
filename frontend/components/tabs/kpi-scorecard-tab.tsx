"use client";

import { useEffect, useState } from "react";
import { AlertTriangle } from "lucide-react";
import { useKpiScorecard } from "@/lib/queries";
import { useSelectionStore } from "@/lib/store";
import {
  changeDirection,
  formatCrore,
  formatIndianNumber,
  formatMultiple,
  formatPercent,
  formatRupees,
  type Unit,
} from "@/lib/format";
import type { KpiScorecardEntry } from "@/lib/api";
import { cn } from "@/lib/utils";

// A falling value is the GOOD direction for these KPIs (fewer days tied
// up, less leverage) -- colouring a QoQ delta purely by arithmetic sign
// would show red for an improving debtor/inventory-days figure, which is
// backwards for a board-facing scorecard.
const LOWER_IS_BETTER = new Set([
  "debtor_days",
  "inventory_days",
  "net_debt_to_ebitda",
  "working_capital_days",
]);

function formatValue(entry: KpiScorecardEntry, unit: Unit): string {
  if (entry.value == null) return "—";
  switch (entry.unit) {
    case "pct":
    case "pp":
      return formatPercent(entry.value, 1);
    case "inr_cr":
      return formatCrore(entry.value, unit, 0);
    case "inr":
      return formatRupees(entry.value, 2);
    case "days":
      return `${formatIndianNumber(entry.value, 0)} days`;
    case "x":
      return formatMultiple(entry.value, 2);
    default:
      return formatIndianNumber(entry.value, 1);
  }
}

function formatDelta(entry: KpiScorecardEntry): string | null {
  // A margin/rate KPI's delta is already in percentage points -- shown as
  // "+1.1pp", never re-expressed as a relative % change (ambiguous for a
  // rate: "margin up 10%" could mean 10 points or 10% relative).
  if (entry.qoq_delta == null) return null;
  const isRateDelta = entry.unit === "pct" || entry.unit === "pp";
  if (isRateDelta && entry.qoq_delta_pct == null) {
    return `${entry.qoq_delta >= 0 ? "+" : ""}${formatIndianNumber(entry.qoq_delta, 1)}pp`;
  }
  if (entry.qoq_delta_pct != null) {
    return `${entry.qoq_delta_pct >= 0 ? "+" : ""}${formatIndianNumber(entry.qoq_delta_pct, 1)}%`;
  }
  return `${entry.qoq_delta >= 0 ? "+" : ""}${formatValue({ ...entry, value: entry.qoq_delta }, "crore")}`;
}

function KpiTile({ entry, unit }: { entry: KpiScorecardEntry; unit: Unit }) {
  const delta = formatDelta(entry);
  const signedForColor = LOWER_IS_BETTER.has(entry.key) && entry.qoq_delta != null ? -entry.qoq_delta : entry.qoq_delta;
  const direction = changeDirection(signedForColor);
  // A handful of KPIs fall back to year-over-year (two annual periods)
  // when this free source doesn't report quarterly cash flow at all for
  // the symbol -- see kpi_scorecard_engine.py. Labelling the delta "QoQ"
  // in that case would misstate what's actually being compared.
  const deltaPeriodLabel = entry.label.includes("(Annual)") ? "YoY" : "QoQ";

  return (
    <div className="rounded-lg border border-border bg-surface p-3">
      <div className="text-xs text-muted">{entry.label}</div>
      {entry.method === "unavailable" ? (
        <>
          <div className="mt-1 text-sm italic text-muted">Not available</div>
          {entry.reason && <p className="mt-1 text-[11px] leading-snug text-muted">{entry.reason}</p>}
        </>
      ) : (
        <>
          <div className="mt-1 tabular-nums-fixed text-lg font-semibold">{formatValue(entry, unit)}</div>
          {delta && (
            <span
              className={cn(
                "tabular-nums-fixed text-xs",
                direction === "up" && "text-up",
                direction === "down" && "text-down",
                direction === "flat" && "text-muted"
              )}
            >
              {delta} {deltaPeriodLabel}
            </span>
          )}
          {entry.reason && (
            <p className="mt-1 flex items-start gap-1 text-[11px] leading-snug text-amber-600 dark:text-amber-400">
              <AlertTriangle size={11} className="mt-0.5 shrink-0" /> {entry.reason}
            </p>
          )}
          {entry.driver_note && <p className="mt-1 text-[11px] leading-snug text-muted">{entry.driver_note}</p>}
        </>
      )}
    </div>
  );
}

const COMMENTARY_STORAGE_PREFIX = "kpi-scorecard-commentary:";

function CommentaryBox({ groupName }: { groupName: string }) {
  const storageKey = `${COMMENTARY_STORAGE_PREFIX}${groupName}`;
  const [value, setValue] = useState("");
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    try {
      setValue(window.localStorage.getItem(storageKey) ?? "");
    } catch {
      // localStorage unavailable (private browsing, etc.) -- commentary
      // just won't persist across reloads, not worth surfacing an error for.
    }
    setLoaded(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [storageKey]);

  return (
    <div className="mt-3">
      <label className="text-[11px] font-medium uppercase tracking-wide text-muted">
        Management commentary
      </label>
      <textarea
        value={loaded ? value : ""}
        onChange={(e) => {
          setValue(e.target.value);
          try {
            window.localStorage.setItem(storageKey, e.target.value);
          } catch {
            // Best-effort persistence only -- see the load-side comment above.
          }
        }}
        placeholder="What's driving this trend, risks to watch, and actions underway -- add before the board meeting."
        rows={2}
        className="mt-1 w-full resize-y rounded-md border border-border bg-background px-2 py-1.5 text-xs text-foreground placeholder:text-muted"
      />
    </div>
  );
}

export function KpiScorecardTab({ symbol }: { symbol: string; template: string }) {
  const { data, isLoading, error } = useKpiScorecard(symbol);
  const unit = useSelectionStore((s) => s.unit);

  if (isLoading) {
    return <div className="text-sm text-muted">Loading KPI scorecard…</div>;
  }
  if (error || !data) {
    return <div className="text-sm text-down">Could not load the KPI scorecard.</div>;
  }

  return (
    <div className="space-y-4">
      <div className="rounded-lg border border-border bg-surface p-3 text-sm">
        <span className="font-medium">{data.quarter_label ?? "Latest quarter"}</span>
        {data.prior_quarter_label && (
          <span className="text-muted"> vs {data.prior_quarter_label}</span>
        )}
      </div>

      {(data.warnings ?? []).length > 0 && (
        <div className="rounded-lg border border-warning-border bg-warning-bg p-3 text-xs text-warning-foreground">
          {(data.warnings ?? []).map((w, i) => (
            <div key={i}>{w}</div>
          ))}
        </div>
      )}

      {data.groups.map((group) => (
        <div key={group.name} className="rounded-lg border border-border bg-surface p-4">
          <h3 className="mb-2 text-sm font-medium">{group.name}</h3>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {group.entries.map((entry) => (
              <KpiTile key={entry.key} entry={entry} unit={unit} />
            ))}
          </div>
          <CommentaryBox groupName={group.name} />
        </div>
      ))}

      <p className="text-xs text-muted">
        The most effective board packs explain why a number moved, what risks are emerging, and what
        management is doing about it -- not just the number itself. The driver notes above are derived
        mechanically from the figures shown; the commentary boxes are where that judgement belongs.
      </p>
    </div>
  );
}
