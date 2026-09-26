"use client";

import { RatioCard } from "@/components/ratio-card";
import type { RatioGroup } from "@/lib/ratio-groups";
import type { GlossaryResponse, RatiosResponse } from "@/lib/api";
import type { Unit } from "@/lib/format";

export function RatioCardGroup({
  group,
  ratios,
  glossary,
  comparableFrom,
  unit,
}: {
  group: RatioGroup;
  ratios: RatiosResponse;
  glossary: GlossaryResponse | undefined;
  comparableFrom: string | null;
  unit: Unit;
}) {
  return (
    <div>
      <h4 className="mb-2 text-xs font-medium uppercase tracking-wide text-muted">{group.label}</h4>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
        {group.ratios.map((def) => (
          <RatioCard
            key={def.key}
            def={def}
            ratio={ratios.ratios[def.key]}
            history={(ratios.history ?? {})[def.key] ?? []}
            comparableFrom={comparableFrom}
            glossary={glossary?.entries[def.key]}
            peerBasis={ratios.peer_basis}
            peerCount={ratios.peer_count}
            unit={unit}
          />
        ))}
      </div>
    </div>
  );
}
