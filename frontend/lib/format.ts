/**
 * Indian number/currency formatting. Every formatter here treats
 * null/undefined as "no data" and renders the em-dash placeholder, never
 * 0 or NaN -- matching the backend's own "missing is null, never 0"
 * convention (see backend/CLAUDE.md).
 */

export const MISSING_VALUE_PLACEHOLDER = "—"; // em dash: "—"
// "Not meaningful" -- distinct from missing data (PLAN.md "Phase 4.2
// review"): the inputs were present, but the computation itself isn't a
// sensible percentage (e.g. growth from a non-positive base). Shown
// instead of MISSING_VALUE_PLACEHOLDER whenever the API/a pure function
// tags a null value with reason "not_meaningful" rather than "missing".
export const NOT_MEANINGFUL_PLACEHOLDER = "n.m.";

export type Unit = "crore" | "lakh_crore";

/** Indian digit grouping: last 3 digits, then groups of 2 (₹12,34,567). */
export function formatIndianNumber(value: number | null | undefined, fractionDigits = 0): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return MISSING_VALUE_PLACEHOLDER;
  }
  return new Intl.NumberFormat("en-IN", {
    maximumFractionDigits: fractionDigits,
    minimumFractionDigits: fractionDigits,
  }).format(value);
}

/** ₹ prefixed Indian-grouped number, e.g. "₹12,34,567.50". */
export function formatRupees(value: number | null | undefined, fractionDigits = 2): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return MISSING_VALUE_PLACEHOLDER;
  }
  return `₹${formatIndianNumber(value, fractionDigits)}`;
}

/**
 * `value` is assumed to already be in Rs crore (this app's internal
 * currency convention -- see backend/app/services/normalize.py). Renders
 * as "₹ Cr" or converts to "₹ L Cr" (lakh crore = 1e5 crore) depending on
 * `unit`.
 */
export function formatCrore(
  value: number | null | undefined,
  unit: Unit = "crore",
  fractionDigits = 2
): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return MISSING_VALUE_PLACEHOLDER;
  }
  if (unit === "lakh_crore") {
    return `₹${formatIndianNumber(value / 100000, fractionDigits)} L Cr`;
  }
  return `₹${formatIndianNumber(value, fractionDigits)} Cr`;
}

/** Auto-picks crore vs lakh-crore based on magnitude (>=1 lakh crore switches). */
export function formatCroreAuto(value: number | null | undefined, fractionDigits = 2): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return MISSING_VALUE_PLACEHOLDER;
  }
  if (Math.abs(value) >= 100000) {
    return formatCrore(value, "lakh_crore", fractionDigits);
  }
  return formatCrore(value, "crore", fractionDigits);
}

/** "12.34%" or "—". */
export function formatPercent(value: number | null | undefined, fractionDigits = 2): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return MISSING_VALUE_PLACEHOLDER;
  }
  return `${formatIndianNumber(value, fractionDigits)}%`;
}

/** "1.84x" or "—" -- for ratios conventionally shown as a multiple (P/E, P/B, D/E). */
export function formatMultiple(value: number | null | undefined, fractionDigits = 2): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return MISSING_VALUE_PLACEHOLDER;
  }
  return `${formatIndianNumber(value, fractionDigits)}x`;
}

export type ChangeDirection = "up" | "down" | "flat";

export function changeDirection(value: number | null | undefined): ChangeDirection {
  if (value === null || value === undefined || Number.isNaN(value) || value === 0) {
    return "flat";
  }
  return value > 0 ? "up" : "down";
}

/** ▲/▼ glyph for a gain/loss -- shown alongside colour, never colour alone. */
export function changeGlyph(value: number | null | undefined): string {
  const direction = changeDirection(value);
  if (direction === "up") return "▲"; // ▲
  if (direction === "down") return "▼"; // ▼
  return "";
}

/**
 * Indian fiscal year label: FY runs Apr-Mar, and is labelled by the
 * calendar year it ENDS in (FY24 = Apr 2023-Mar 2024). `periodEnd` is an
 * ISO date string (e.g. from the backend's FinancialPeriod.period_end).
 * Mirrors backend/app/services/normalize.py's `_fiscal_year_label` exactly
 * -- keep the two in sync if either changes.
 */
export function fiscalYearLabel(periodEnd: string): string {
  const date = new Date(periodEnd);
  let year = date.getUTCFullYear();
  if (date.getUTCMonth() + 1 > 3) {
    // getUTCMonth() is 0-indexed; +1 to match "month > 3" i.e. after March
    year += 1;
  }
  return `FY${String(year % 100).padStart(2, "0")}`;
}

/** en-dash-separated day/52-week range: "₹1,234.50 – ₹1,876.00". */
export function formatRange(
  low: number | null | undefined,
  high: number | null | undefined,
  fractionDigits = 2
): string {
  if (low === null || low === undefined || high === null || high === undefined) {
    return MISSING_VALUE_PLACEHOLDER;
  }
  return `${formatRupees(low, fractionDigits)} – ${formatRupees(high, fractionDigits)}`;
}
