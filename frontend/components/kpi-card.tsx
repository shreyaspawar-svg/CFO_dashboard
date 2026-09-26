import { formatCrore, formatIndianNumber, formatMultiple, formatPercent, type Unit } from "@/lib/format";
import type { KpiDef } from "@/lib/kpi-templates";
import type { RatioValue } from "@/lib/api";

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

export function KpiCard({ def, ratio, unit }: { def: KpiDef; ratio: RatioValue | undefined; unit: Unit }) {
  const format = formatterFor(def.format, unit);

  return (
    <div className="rounded-lg border border-border bg-surface p-3">
      <div className="text-xs text-muted">{def.label}</div>
      {!def.available ? (
        <div className="mt-1 text-sm text-muted" title="Not in free data source">
          {"—"}
        </div>
      ) : (
        <>
          <div className="mt-1 text-lg font-semibold tabular-nums-fixed">{format(ratio?.value)}</div>
          {ratio?.peer_median !== undefined && ratio?.peer_median !== null && (
            <div className="text-xs text-muted tabular-nums-fixed">
              Sector median: {format(ratio.peer_median)}
            </div>
          )}
        </>
      )}
    </div>
  );
}
