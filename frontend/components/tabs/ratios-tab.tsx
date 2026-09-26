"use client";

import { useFinancials, useGlossary, useRatios } from "@/lib/queries";
import { useSelectionStore } from "@/lib/store";
import { ratioGroupsFor } from "@/lib/ratio-groups";
import { RatioCardGroup } from "@/components/ratio-card-group";
import { StrengthsWatchouts } from "@/components/strengths-watchouts";
import { DupontChart } from "@/components/charts/dupont-chart";
import { RatioHeatmapChart } from "@/components/charts/ratio-heatmap-chart";
import { PeerStripChart } from "@/components/charts/peer-strip-chart";
import { QualityScoresPanel } from "@/components/quality-scores";
import { ErrorBoundary } from "@/components/error-boundary";

export function RatiosTab({ symbol, template }: { symbol: string; template: string }) {
  const { data: ratios, isLoading } = useRatios(symbol);
  const { data: glossary } = useGlossary();
  const { data: financials } = useFinancials(symbol, "annual");
  const unit = useSelectionStore((s) => s.unit);

  if (isLoading || !ratios) {
    return <div className="h-96 animate-pulse rounded-lg border border-border bg-surface" />;
  }

  const comparableFrom = financials?.comparable_from ?? null;
  const groups = ratioGroupsFor(template);

  return (
    <div className="space-y-4">
      <ErrorBoundary region="strengths and watch-outs">
        <StrengthsWatchouts signals={ratios.signals ?? []} />
      </ErrorBoundary>

      {groups.map((group) => (
        <ErrorBoundary key={group.label} region={`ratio group: ${group.label}`}>
          <RatioCardGroup
            group={group}
            ratios={ratios}
            glossary={glossary}
            comparableFrom={comparableFrom}
            unit={unit}
          />
        </ErrorBoundary>
      ))}

      <ErrorBoundary region="dupont decomposition">
        <DupontChart symbol={symbol} ratios={ratios} comparableFrom={comparableFrom} template={template} />
      </ErrorBoundary>

      <ErrorBoundary region="ratio history heatmap">
        <RatioHeatmapChart symbol={symbol} template={template} ratios={ratios} comparableFrom={comparableFrom} />
      </ErrorBoundary>

      <ErrorBoundary region="peer strip plot">
        <PeerStripChart symbol={symbol} template={template} />
      </ErrorBoundary>

      <div>
        <h3 className="mb-2 text-sm font-medium">Quality scores</h3>
        <ErrorBoundary region="quality scores">
          <QualityScoresPanel scores={ratios.quality_scores} />
        </ErrorBoundary>
      </div>
    </div>
  );
}
