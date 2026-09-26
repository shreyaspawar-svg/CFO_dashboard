import type { Template } from "@/lib/kpi-templates";

export interface FinancialPeriodLite {
  fiscal_year: string;
  period_end: string;
  line_items: Record<string, number | null | undefined>;
}

/** `(numerator / denominator) * 100`, `null` for a missing or zero
 * denominator -- never a fabricated 0 or an Infinity/NaN a chart would
 * render as a stray point. */
export function marginPct(
  numerator: number | null | undefined,
  denominator: number | null | undefined
): number | null {
  if (numerator === null || numerator === undefined || !denominator) return null;
  return (numerator / denominator) * 100;
}

export interface GrowthPoint {
  label: string;
  growthPct: number | null;
}

/** True if `prevPeriodEnd` and `currPeriodEnd` sit on opposite sides of a
 * corporate-action cutoff -- a growth rate across that boundary isn't
 * organic growth, it's a change in what's being measured (PLAN.md "Phase
 * 1.5 review" item 2, same principle the backend's `comparable_periods`
 * already applies to CAGR/health-radar figures). `comparableFrom` is
 * `/api/financials`' `comparable_from` field; `null` means no cutoff. */
function straddlesCutoff(prevPeriodEnd: string, currPeriodEnd: string, comparableFrom: string | null): boolean {
  if (!comparableFrom) return false;
  return prevPeriodEnd < comparableFrom && currPeriodEnd >= comparableFrom;
}

/** YoY/QoQ growth for one line item across consecutive periods (oldest
 * first, matching `/api/financials`' own ordering). The first period has
 * no prior point to compare against (`growthPct: null`), as does any pair
 * whose prior value is missing, zero, or that straddles a comparable_from
 * cutoff. */
export function computeGrowthSeries(
  periods: FinancialPeriodLite[],
  key: string,
  comparableFrom: string | null
): GrowthPoint[] {
  return periods.map((period, i) => {
    if (i === 0) return { label: period.fiscal_year, growthPct: null };
    const prev = periods[i - 1];
    const prevValue = prev.line_items[key];
    const currValue = period.line_items[key];
    if (
      prevValue === null ||
      prevValue === undefined ||
      currValue === null ||
      currValue === undefined ||
      // A growth % from a non-positive base isn't meaningful, not just
      // visually extreme: swinging from -300 to +8,000 is a sign change,
      // not "+2,600% growth" -- the formula's sign flips backwards for a
      // negative base (a move from -100 to -50 is really an improvement,
      // but the raw formula reports -50%). Standard analyst convention is
      // "n/m" (not meaningful) here, same principle as this app's own
      // P/E-from-near-zero-EPS plausibility guard (backend/docs/data-notes.md).
      prevValue <= 0 ||
      straddlesCutoff(prev.period_end, period.period_end, comparableFrom)
    ) {
      return { label: period.fiscal_year, growthPct: null };
    }
    return { label: period.fiscal_year, growthPct: ((currValue - prevValue) / prevValue) * 100 };
  });
}

/** CAGR of a line item across only the comparable periods (>= comparableFrom,
 * or all periods when there's no cutoff) -- mirrors the backend metrics
 * engine's own `_years_between`/CAGR approach, over whatever span the data
 * actually covers (PLAN.md "Phase 1.5 review" item 4: don't imply a 5-year
 * CAGR from 3 years of data). Returns `null` for a sub-1-year span, same
 * guard as `computeReturnsTable`. */
export function computeSeriesCagr(
  periods: FinancialPeriodLite[],
  key: string,
  comparableFrom: string | null
): number | null {
  const comparable = comparableFrom
    ? periods.filter((p) => p.period_end >= comparableFrom)
    : periods;
  if (comparable.length < 2) return null;
  const first = comparable[0];
  const last = comparable[comparable.length - 1];
  const firstValue = first.line_items[key];
  const lastValue = last.line_items[key];
  if (
    firstValue === null ||
    firstValue === undefined ||
    lastValue === null ||
    lastValue === undefined ||
    firstValue <= 0 ||
    lastValue <= 0
  ) {
    return null;
  }
  const years =
    (new Date(last.period_end).getTime() - new Date(first.period_end).getTime()) / (365.25 * 24 * 60 * 60 * 1000);
  if (years < 0.95) return null;
  return (Math.pow(lastValue / firstValue, 1 / years) - 1) * 100;
}

export interface WaterfallStep {
  label: string;
  /** The bar's own height (can be negative for a subtraction step). */
  delta: number;
  /** Cumulative value this step lands on -- used to position the bar. */
  cumulative: number;
  isTotal: boolean;
}

/** Template-aware waterfall for one period (PLAN.md §4.2: "a bank/NBFC/
 * insurer template has no COGS/Opex split the way a general company does
 * -- show NII/NIM-based line items instead"). Only includes a step when
 * its underlying line item is actually present -- never fabricates a
 * value to keep the chart's shape complete (§2's "—" convention). */
export function computeWaterfallSteps(period: FinancialPeriodLite, template: Template): WaterfallStep[] {
  const li = period.line_items;
  const steps: WaterfallStep[] = [];
  let cumulative = 0;

  const addTotal = (label: string, value: number | null | undefined) => {
    if (value === null || value === undefined) return false;
    cumulative = value;
    steps.push({ label, delta: value, cumulative, isTotal: true });
    return true;
  };
  const addDelta = (label: string, delta: number | null | undefined) => {
    if (delta === null || delta === undefined || delta === 0) return false;
    const next = cumulative + delta;
    steps.push({ label, delta, cumulative: next, isTotal: false });
    cumulative = next;
    return true;
  };

  if (template === "bank" || template === "nbfc" || template === "insurance") {
    // Branch strictly on template, not on which field happens to be
    // non-null: an insurer can carry a small, non-null `net_interest_income`
    // from its investment book that isn't its headline top line the way it
    // is for a bank/NBFC -- `??` would silently pick that instead of the
    // real ~Rs90,000 Cr `premiums_earned` figure and start the waterfall
    // from the wrong number entirely.
    const startingValue = template === "insurance" ? li.premiums_earned : li.net_interest_income;
    if (!addTotal(template === "insurance" ? "Premiums earned" : "Net interest income", startingValue)) {
      return [];
    }
    addDelta("Non-interest income", li.non_interest_income);
    addDelta("Non-interest expense", li.non_interest_expense != null ? -Math.abs(li.non_interest_expense) : null);
    addDelta("Tax", li.tax != null ? -Math.abs(li.tax) : null);
    if (li.net_income != null) {
      steps.push({ label: "Net income", delta: 0, cumulative: li.net_income, isTotal: true });
    }
    return steps;
  }

  if (!addTotal("Revenue", li.revenue)) return [];
  addDelta("COGS", li.cogs != null ? -Math.abs(li.cogs) : null);
  if (li.gross_profit != null) {
    steps.push({ label: "Gross profit", delta: 0, cumulative: li.gross_profit, isTotal: true });
    cumulative = li.gross_profit;
  }
  // Opex isn't a directly mapped line item -- derived as the gap between
  // gross profit and EBITDA, only when both are present (never fabricated).
  if (li.gross_profit != null && li.ebitda != null) {
    addDelta("Opex (derived)", -(li.gross_profit - li.ebitda));
  }
  if (li.ebitda != null) {
    steps.push({ label: "EBITDA", delta: 0, cumulative: li.ebitda, isTotal: true });
    cumulative = li.ebitda;
  }
  addDelta("D&A", li.d_and_a != null ? -Math.abs(li.d_and_a) : null);
  if (li.ebit != null) {
    steps.push({ label: "EBIT", delta: 0, cumulative: li.ebit, isTotal: true });
    cumulative = li.ebit;
  }
  // The EBIT -> Pretax step can include non-operating items beyond
  // interest expense alone -- label it by what's actually being reported
  // (the real gap), not just "Interest", so nothing is implied that isn't
  // in the data.
  if (li.pretax_income != null) {
    const label = li.interest_expense != null ? "Interest & other" : "Other";
    addDelta(label, li.pretax_income - cumulative);
    steps.push({ label: "Pretax income", delta: 0, cumulative: li.pretax_income, isTotal: true });
    cumulative = li.pretax_income;
  }
  addDelta("Tax", li.tax != null ? -Math.abs(li.tax) : null);
  if (li.net_income != null) {
    steps.push({ label: "Net income", delta: 0, cumulative: li.net_income, isTotal: true });
  }
  return steps;
}
