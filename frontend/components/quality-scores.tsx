import { Check, X, HelpCircle } from "lucide-react";
import { cn } from "@/lib/utils";
import type { QualityScores } from "@/lib/api";

const ZONE_LABEL: Record<string, string> = {
  safe: "Safe zone",
  grey: "Grey zone",
  distress: "Distress zone",
};

const ZONE_COLOR: Record<string, string> = {
  safe: "text-up",
  grey: "text-amber-500",
  distress: "text-down",
};

/** Altman Z (5 components + zone) and Piotroski F (9-test checklist) --
 * PLAN.md §4.3 item 6. Hidden entirely for bank/NBFC/insurance templates
 * (no current_assets/liabilities concept), which is signalled by
 * `scores` being `undefined`/`null` from the backend, not computed here. */
export function QualityScoresPanel({ scores }: { scores: QualityScores | null | undefined }) {
  if (!scores) {
    return (
      <div className="rounded-lg border border-border bg-surface p-4 text-sm text-muted">
        Not applicable to financial companies.
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
      <div className="rounded-lg border border-border bg-surface p-4">
        <div className="mb-2 flex items-center justify-between">
          <h3 className="text-sm font-medium">Altman Z-Score</h3>
          {scores.altman.zone && (
            <span className={cn("text-xs font-medium", ZONE_COLOR[scores.altman.zone])}>
              {ZONE_LABEL[scores.altman.zone]}
            </span>
          )}
        </div>
        <div className="text-2xl font-semibold tabular-nums-fixed">
          {scores.altman.score != null ? scores.altman.score.toFixed(2) : "—"}
        </div>
        <ul className="mt-3 space-y-1 text-xs text-muted">
          {scores.altman.components.map((c) => (
            <li key={c.label} className="flex justify-between tabular-nums-fixed">
              <span>{c.label}</span>
              <span>{c.value != null ? c.value.toFixed(2) : "—"}</span>
            </li>
          ))}
        </ul>
      </div>

      <div className="rounded-lg border border-border bg-surface p-4">
        <div className="mb-2 flex items-center justify-between">
          <h3 className="text-sm font-medium">Piotroski F-Score</h3>
          {scores.piotroski && (
            <span className="text-xs text-muted tabular-nums-fixed">
              {scores.piotroski.earned}/{scores.piotroski.possible}
            </span>
          )}
        </div>
        {!scores.piotroski ? (
          <p className="text-sm text-muted">Not enough comparable periods.</p>
        ) : (
          <ul className="space-y-1 text-xs">
            {scores.piotroski.tests.map((t) => (
              <li key={t.label} className="flex items-center gap-2">
                {t.passed === true ? (
                  <Check size={13} className="shrink-0 text-up" />
                ) : t.passed === false ? (
                  <X size={13} className="shrink-0 text-down" />
                ) : (
                  <HelpCircle size={13} className="shrink-0 text-muted" />
                )}
                <span className={t.passed == null ? "text-muted" : ""}>{t.label}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
