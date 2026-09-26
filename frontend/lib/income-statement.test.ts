import { describe, expect, it } from "vitest";
import {
  computeGrowthSeries,
  computeSeriesCagr,
  computeWaterfallSteps,
  type FinancialPeriodLite,
} from "./income-statement";

function period(fiscal_year: string, period_end: string, line_items: Record<string, number | null>): FinancialPeriodLite {
  return { fiscal_year, period_end, line_items };
}

describe("computeGrowthSeries", () => {
  const periods = [
    period("FY23", "2023-03-31", { revenue: 100 }),
    period("FY24", "2024-03-31", { revenue: 110 }),
    period("FY25", "2025-03-31", { revenue: 121 }),
  ];

  it("has no growth for the first (oldest) period", () => {
    const result = computeGrowthSeries(periods, "revenue", null);
    expect(result[0]).toEqual({ label: "FY23", growthPct: null });
  });

  it("computes YoY growth for subsequent periods", () => {
    const result = computeGrowthSeries(periods, "revenue", null);
    expect(result[1].growthPct).toBeCloseTo(10, 5);
    expect(result[2].growthPct).toBeCloseTo(10, 5);
  });

  it("returns null growth for a missing value on either side", () => {
    const withGap = [period("FY23", "2023-03-31", { revenue: null }), period("FY24", "2024-03-31", { revenue: 110 })];
    expect(computeGrowthSeries(withGap, "revenue", null)[1].growthPct).toBeNull();
  });

  it("treats growth from a non-positive base as not meaningful (null), not an extreme percentage", () => {
    // INDIGO-shaped: net income swings from -305.79 to +8172.50 -- the raw
    // formula would report an extreme, sign-inverted "+2673%" that isn't a
    // meaningful growth figure.
    const swingy = [
      period("FY23", "2023-03-31", { net_income: -305.79 }),
      period("FY24", "2024-03-31", { net_income: 8172.5 }),
    ];
    expect(computeGrowthSeries(swingy, "net_income", null)[1].growthPct).toBeNull();
  });

  it("excludes growth across a comparable_from cutoff, not just before/after it individually", () => {
    // HDFCBANK-shaped: FY23 pre-merger, FY24 onward post-merger -- the FY23->FY24
    // "growth" would be a corporate-action jump, not organic growth.
    const result = computeGrowthSeries(periods, "revenue", "2023-04-01");
    expect(result[1].growthPct).toBeNull(); // FY23 -> FY24 straddles the cutoff
    expect(result[2].growthPct).toBeCloseTo(10, 5); // FY24 -> FY25 is fully post-cutoff
  });
});

describe("computeSeriesCagr", () => {
  const periods = [
    period("FY22", "2022-03-31", { revenue: 100 }),
    period("FY23", "2023-03-31", { revenue: 110 }),
    period("FY24", "2024-03-31", { revenue: 121 }),
  ];

  it("computes CAGR across the full comparable span", () => {
    const cagr = computeSeriesCagr(periods, "revenue", null);
    expect(cagr).toBeCloseTo(10, 0);
  });

  it("only uses periods at or after comparable_from", () => {
    // Only FY23->FY24 (10%) should count, not FY22's lower base.
    const cagr = computeSeriesCagr(periods, "revenue", "2023-01-01");
    expect(cagr).toBeCloseTo(10, 0);
  });

  it("returns null with fewer than 2 comparable periods", () => {
    expect(computeSeriesCagr(periods, "revenue", "2024-01-01")).toBeNull();
  });

  it("returns null for a negative or zero base value", () => {
    const negative = [period("FY22", "2022-03-31", { revenue: -50 }), period("FY24", "2024-03-31", { revenue: 100 })];
    expect(computeSeriesCagr(negative, "revenue", null)).toBeNull();
  });
});

describe("computeWaterfallSteps", () => {
  it("builds a general-template waterfall from available line items", () => {
    const p = period("FY25", "2025-03-31", {
      revenue: 1000,
      cogs: 600,
      gross_profit: 400,
      ebitda: 250,
      d_and_a: 50,
      ebit: 200,
      interest_expense: 20,
      pretax_income: 180,
      tax: 45,
      net_income: 135,
    });
    const steps = computeWaterfallSteps(p, "general");
    const labels = steps.map((s) => s.label);
    expect(labels).toContain("Revenue");
    expect(labels).toContain("Gross profit");
    expect(labels).toContain("EBITDA");
    expect(labels).toContain("EBIT");
    expect(labels).toContain("Net income");
    const netIncomeStep = steps.find((s) => s.label === "Net income");
    expect(netIncomeStep?.cumulative).toBe(135);
  });

  it("returns an empty list rather than a broken chart when revenue itself is missing", () => {
    const p = period("FY25", "2025-03-31", { revenue: null });
    expect(computeWaterfallSteps(p, "general")).toEqual([]);
  });

  it("skips a derived Opex step when EBITDA is unavailable, without fabricating a value", () => {
    const p = period("FY25", "2025-03-31", { revenue: 1000, cogs: 600, gross_profit: 400, ebitda: null });
    const steps = computeWaterfallSteps(p, "general");
    expect(steps.some((s) => s.label.startsWith("Opex"))).toBe(false);
  });

  it("uses premiums_earned for an insurance template even when a stray non-null NII value is present", () => {
    // Regression: an insurer can carry a small non-null net_interest_income
    // from its investment book; `??`-style fallback would wrongly start the
    // waterfall from that instead of the real headline premiums figure.
    const p = period("FY26", "2026-03-31", {
      net_interest_income: -150,
      premiums_earned: 91606,
      tax: 100,
      net_income: 1912,
    });
    const steps = computeWaterfallSteps(p, "insurance");
    expect(steps[0]).toEqual({ label: "Premiums earned", delta: 91606, cumulative: 91606, isTotal: true });
  });

  it("builds a bank-template waterfall from NII, not COGS/Opex", () => {
    const p = period("FY25", "2025-03-31", {
      net_interest_income: 500,
      non_interest_income: 100,
      non_interest_expense: 300,
      tax: 75,
      net_income: 225,
    });
    const steps = computeWaterfallSteps(p, "bank");
    const labels = steps.map((s) => s.label);
    expect(labels).toEqual(["Net interest income", "Non-interest income", "Non-interest expense", "Tax", "Net income"]);
    expect(steps.find((s) => s.label === "Net income")?.cumulative).toBe(225);
  });
});
