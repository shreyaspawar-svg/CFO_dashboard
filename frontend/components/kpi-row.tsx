"use client";

import { useRatios } from "@/lib/queries";
import { headlineKpis } from "@/lib/kpi-templates";
import { KpiCard } from "@/components/kpi-card";
import { KpiRowSkeleton } from "@/components/skeletons";
import { useSelectionStore } from "@/lib/store";

export function KpiRow({ symbol, template }: { symbol: string; template: string }) {
  const { data: ratios, isLoading } = useRatios(symbol);
  const unit = useSelectionStore((s) => s.unit);

  if (isLoading || !ratios) return <KpiRowSkeleton />;

  const defs = headlineKpis(template);

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
      {defs.map((def) => (
        <KpiCard key={def.key} def={def} ratio={ratios.ratios[def.key]} unit={unit} />
      ))}
    </div>
  );
}
