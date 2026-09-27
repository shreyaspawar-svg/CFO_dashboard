/** Simple moving average, computed client-side from `/api/history` closes
 * (Phase 4 §4.1: "computed from /api/history, not fetched"). Returns one
 * value per input point, `null` for the leading points that don't yet have
 * `period` prior closes -- never a fabricated partial average. */
export function simpleMovingAverage(closes: (number | null)[], period: number): (number | null)[] {
  const result: (number | null)[] = new Array(closes.length).fill(null);
  for (let i = period - 1; i < closes.length; i++) {
    const window = closes.slice(i - period + 1, i + 1);
    if (window.some((v) => v === null)) continue;
    const sum = (window as number[]).reduce((a, b) => a + b, 0);
    result[i] = sum / period;
  }
  return result;
}

export interface ReturnPoint {
  label: string;
  days: number;
}

// Not all of these will have enough history to compute (PLAN.md "Phase 1
// review" item 4: Yahoo gives ~4 annual years of financials, but daily
// price history usually goes back further) -- computeReturnsTable returns
// `null` for any span longer than the data actually covers, rather than
// silently truncating the label.
export const RETURN_SPANS: ReturnPoint[] = [
  { label: "1M", days: 30 },
  { label: "3M", days: 91 },
  { label: "6M", days: 182 },
  { label: "1Y", days: 365 },
  { label: "3Y", days: 365 * 3 },
  { label: "5Y", days: 365 * 5 },
];

export interface ReturnsRow {
  label: string;
  returnPct: number | null;
  /** CAGR only makes sense beyond ~1 year; shorter spans get null here. */
  cagrPct: number | null;
}

/** `bars` oldest-first, each with a `date` (ISO) and `close`. */
export function computeReturnsTable(
  bars: { date: string; close: number | null }[],
  spans: ReturnPoint[] = RETURN_SPANS
): ReturnsRow[] {
  if (bars.length === 0) return spans.map((s) => ({ label: s.label, returnPct: null, cagrPct: null }));

  const latest = bars[bars.length - 1];
  const latestDate = new Date(latest.date).getTime();
  if (latest.close === null) {
    return spans.map((s) => ({ label: s.label, returnPct: null, cagrPct: null }));
  }

  return spans.map((span) => {
    const targetTime = latestDate - span.days * 24 * 60 * 60 * 1000;
    // Earliest bar at or after targetTime -- the closest available point
    // without reaching further back than the data actually goes.
    const startBar = bars.find((b) => new Date(b.date).getTime() >= targetTime);
    if (!startBar || startBar.close === null || startBar.close === 0 || startBar === latest) {
      return { label: span.label, returnPct: null, cagrPct: null };
    }
    const actualDays = (latestDate - new Date(startBar.date).getTime()) / (24 * 60 * 60 * 1000);
    // The data doesn't actually reach back this far (the earliest bar is
    // the oldest one available, not a real ~span.days-ago point) -- don't
    // imply history that isn't there (PLAN.md "Phase 1 review" item 4).
    if (actualDays < span.days * 0.9) {
      return { label: span.label, returnPct: null, cagrPct: null };
    }
    const returnPct = ((latest.close as number) - startBar.close) / startBar.close * 100;
    const years = actualDays / 365.25;
    const cagrPct =
      years >= 0.95 && startBar.close > 0 && (latest.close as number) > 0
        ? (Math.pow((latest.close as number) / startBar.close, 1 / years) - 1) * 100
        : null;
    return { label: span.label, returnPct, cagrPct };
  });
}

/** Evenly spaced indices into a `length`-long axis, always including the
 * first and last, for thinning a category axis's date labels down to
 * ~`targetCount` (PLAN.md Phase 5.1 item 1) -- a 5Y daily price series has
 * ~1250 points, and letting ECharts' own `interval: 'auto'` guess at
 * spacing produced overlapping/illegible labels rather than a clean,
 * fixed tick count regardless of range. Returns fewer than `targetCount`
 * only when `length` itself is smaller. */
export function pickEvenTickIndices(length: number, targetCount = 7): number[] {
  if (length <= 0) return [];
  if (length <= targetCount) return Array.from({ length }, (_, i) => i);
  const step = (length - 1) / (targetCount - 1);
  const indices = new Set<number>();
  for (let i = 0; i < targetCount; i++) {
    indices.add(Math.round(i * step));
  }
  return [...indices].sort((a, b) => a - b);
}

/** An ECharts category-axis `axisLabel.interval` function that shows only
 * the labels at `pickEvenTickIndices(length, targetCount)`. */
export function thinnedTickInterval(length: number, targetCount = 7): (index: number) => boolean {
  const shown = new Set(pickEvenTickIndices(length, targetCount));
  return (index: number) => shown.has(index);
}

/** Aligns two bar series onto one shared date axis by DATE, not array
 * position. Two independently-fetched series (e.g. a stock's bars and the
 * `^NSEI` benchmark's bars from the same `/api/history` response) can have
 * different null-close days -- comparing them index-by-index then silently
 * shifts every later point onto the wrong date the moment the two series'
 * null days diverge. This is the exact bug that produced implausibly-low
 * computed betas backend-side too (PLAN.md "Phase 4.1 review" item 2: `^NSEI`'s
 * own feed has scattered null closes on days a stock trades fine). A date
 * missing from one series becomes `null` there -- a gap (Phase 4.0's "gaps
 * not zeros" rule), not a wrong value. */
export function alignByDate(
  seriesA: { date: string; close?: number | null }[],
  seriesB: { date: string; close?: number | null }[]
): { dates: string[]; a: (number | null)[]; b: (number | null)[] } {
  const byDateA = new Map(seriesA.map((bar) => [bar.date.slice(0, 10), bar.close ?? null]));
  const byDateB = new Map(seriesB.map((bar) => [bar.date.slice(0, 10), bar.close ?? null]));
  const dates = [...new Set([...byDateA.keys(), ...byDateB.keys()])].sort();
  return {
    dates,
    a: dates.map((d) => byDateA.get(d) ?? null),
    b: dates.map((d) => byDateB.get(d) ?? null),
  };
}
