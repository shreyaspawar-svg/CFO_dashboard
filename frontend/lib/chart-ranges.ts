/** Shared range/interval config for the Overview tab's Price and
 * "Performance vs NIFTY 50" charts (PLAN.md Phase 5.1 item 2) -- both
 * charts read the SAME active range so they always show the same window,
 * rather than the Price chart's toggle only affecting itself. */
export const CHART_RANGE_OPTIONS = {
  "1D": { range: "1d", interval: "5m", livePoll: true },
  "1Y": { range: "1y", interval: "1d", livePoll: false },
  "5Y": { range: "5y", interval: "1d", livePoll: false },
} as const;

export type ChartRangeKey = keyof typeof CHART_RANGE_OPTIONS;
