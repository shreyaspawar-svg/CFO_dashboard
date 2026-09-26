import { describe, expect, it } from "vitest";
import {
  changeDirection,
  changeGlyph,
  fiscalYearLabel,
  formatCrore,
  formatCroreAuto,
  formatIndianNumber,
  formatMultiple,
  formatPercent,
  formatRange,
  formatRupees,
  MISSING_VALUE_PLACEHOLDER,
} from "./format";

describe("formatIndianNumber", () => {
  it("groups digits the Indian way", () => {
    expect(formatIndianNumber(1234567)).toBe("12,34,567");
  });

  it("handles small numbers without extra grouping", () => {
    expect(formatIndianNumber(567)).toBe("567");
  });

  it("renders the placeholder for null/undefined/NaN, never 0", () => {
    expect(formatIndianNumber(null)).toBe(MISSING_VALUE_PLACEHOLDER);
    expect(formatIndianNumber(undefined)).toBe(MISSING_VALUE_PLACEHOLDER);
    expect(formatIndianNumber(NaN)).toBe(MISSING_VALUE_PLACEHOLDER);
    expect(formatIndianNumber(0)).not.toBe(MISSING_VALUE_PLACEHOLDER);
    expect(formatIndianNumber(0)).toBe("0");
  });
});

describe("formatRupees", () => {
  it("prefixes with the rupee sign", () => {
    expect(formatRupees(1234567.5)).toBe("₹12,34,567.50");
  });

  it("missing value is the placeholder", () => {
    expect(formatRupees(null)).toBe(MISSING_VALUE_PLACEHOLDER);
  });
});

describe("formatCrore / formatCroreAuto", () => {
  it("formats as crore by default", () => {
    expect(formatCrore(753286)).toBe("₹7,53,286.00 Cr");
  });

  it("converts to lakh crore on request", () => {
    expect(formatCrore(753286, "lakh_crore")).toBe("₹7.53 L Cr");
  });

  it("auto-switches to lakh crore at >= 1,00,000 crore", () => {
    expect(formatCroreAuto(753286)).toContain("L Cr");
    expect(formatCroreAuto(99999)).not.toContain("L Cr");
  });

  it("missing value is the placeholder, not 0 Cr", () => {
    expect(formatCrore(null)).toBe(MISSING_VALUE_PLACEHOLDER);
    expect(formatCroreAuto(undefined)).toBe(MISSING_VALUE_PLACEHOLDER);
  });
});

describe("formatPercent / formatMultiple", () => {
  it("formats percentages and multiples", () => {
    expect(formatPercent(27.07)).toBe("27.07%");
    expect(formatMultiple(7.02)).toBe("7.02x");
  });

  it("missing values are the placeholder", () => {
    expect(formatPercent(null)).toBe(MISSING_VALUE_PLACEHOLDER);
    expect(formatMultiple(undefined)).toBe(MISSING_VALUE_PLACEHOLDER);
  });

  it("negative values are preserved (e.g. negative ROE), not hidden", () => {
    expect(formatPercent(-20, 0)).toBe("-20%");
  });
});

describe("changeDirection / changeGlyph", () => {
  it("classifies up/down/flat", () => {
    expect(changeDirection(5)).toBe("up");
    expect(changeDirection(-5)).toBe("down");
    expect(changeDirection(0)).toBe("flat");
    expect(changeDirection(null)).toBe("flat");
  });

  it("gives a glyph for up/down, none for flat", () => {
    expect(changeGlyph(5)).toBe("▲");
    expect(changeGlyph(-5)).toBe("▼");
    expect(changeGlyph(0)).toBe("");
    expect(changeGlyph(null)).toBe("");
  });
});

describe("fiscalYearLabel", () => {
  it("labels a March period-end by its own calendar year (FY24 = Mar 2024)", () => {
    expect(fiscalYearLabel("2024-03-31")).toBe("FY24");
  });

  it("labels a period ending after March by the FY that closes next March", () => {
    expect(fiscalYearLabel("2023-12-31")).toBe("FY24");
  });

  it("matches the backend's own convention for a two-digit-year rollover", () => {
    expect(fiscalYearLabel("2000-03-31")).toBe("FY00");
  });
});

describe("formatRange", () => {
  it("formats a low-high range with an en dash", () => {
    expect(formatRange(1976.8, 3350)).toBe("₹1,976.80 – ₹3,350.00");
  });

  it("missing either side is the placeholder", () => {
    expect(formatRange(null, 3350)).toBe(MISSING_VALUE_PLACEHOLDER);
    expect(formatRange(1976.8, undefined)).toBe(MISSING_VALUE_PLACEHOLDER);
  });
});
