import { describe, expect, it } from "vitest";
import { marketStatus } from "./market-status";

// Mirrors backend/tests/test_market.py's cases exactly.
function istAsUtc(y: number, mo: number, d: number, h: number, mi: number): Date {
  // Construct the UTC instant equal to that IST wall-clock time.
  const istOffsetMs = (5 * 60 + 30) * 60 * 1000;
  const asIfUtc = Date.UTC(y, mo - 1, d, h, mi);
  return new Date(asIfUtc - istOffsetMs);
}

describe("marketStatus", () => {
  it("is open during trading hours on a weekday", () => {
    // Wed 2026-03-25, 10:00 IST
    expect(marketStatus(istAsUtc(2026, 3, 25, 10, 0))).toBe("open");
  });

  it("is pre_open before 09:15 IST", () => {
    expect(marketStatus(istAsUtc(2026, 3, 25, 9, 5))).toBe("pre_open");
  });

  it("is closed after hours", () => {
    expect(marketStatus(istAsUtc(2026, 3, 25, 16, 0))).toBe("closed");
  });

  it("is closed on a weekend", () => {
    // 2026-03-28 is a Saturday
    expect(marketStatus(istAsUtc(2026, 3, 28, 10, 0))).toBe("closed");
  });
});
