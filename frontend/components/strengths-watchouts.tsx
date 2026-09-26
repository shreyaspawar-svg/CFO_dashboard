import { TrendingUp, AlertCircle } from "lucide-react";
import type { Signal } from "@/lib/api";

/** "Strengths & watch-outs" panel (PLAN.md §4.3 item 7) -- purely a
 * renderer for the backend's rule-based `signals[]`; no client-side logic
 * decides what counts as a strength or a watch-out. */
export function StrengthsWatchouts({ signals }: { signals: Signal[] }) {
  const strengths = signals.filter((s) => s.type === "strength");
  const watches = signals.filter((s) => s.type === "watch");

  if (signals.length === 0) {
    return (
      <div className="rounded-lg border border-border bg-surface p-4 text-sm text-muted">
        No rule-based signals triggered for this company&apos;s current data.
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
      <div className="rounded-lg border border-border bg-surface p-4">
        <h3 className="mb-2 flex items-center gap-1.5 text-sm font-medium text-up">
          <TrendingUp size={14} /> Strengths
        </h3>
        {strengths.length === 0 ? (
          <p className="text-sm text-muted">None triggered.</p>
        ) : (
          <ul className="space-y-2 text-sm">
            {strengths.map((s) => (
              <li key={s.rule}>{s.message}</li>
            ))}
          </ul>
        )}
      </div>
      <div className="rounded-lg border border-border bg-surface p-4">
        <h3 className="mb-2 flex items-center gap-1.5 text-sm font-medium text-down">
          <AlertCircle size={14} /> Watch-outs
        </h3>
        {watches.length === 0 ? (
          <p className="text-sm text-muted">None triggered.</p>
        ) : (
          <ul className="space-y-2 text-sm">
            {watches.map((s) => (
              <li key={s.rule}>{s.message}</li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
