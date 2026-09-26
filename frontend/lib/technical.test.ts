import { describe, expect, it } from "vitest";
import { alignByDate, computeReturnsTable, simpleMovingAverage } from "./technical";

describe("simpleMovingAverage", () => {
  it("computes a basic SMA", () => {
    const closes = [1, 2, 3, 4, 5];
    const sma3 = simpleMovingAverage(closes, 3);
    expect(sma3).toEqual([null, null, 2, 3, 4]);
  });

  it("leaves a gap (null) for a window containing a missing close, not a partial average", () => {
    const closes = [1, 2, null, 4, 5];
    const sma3 = simpleMovingAverage(closes, 3);
    expect(sma3[2]).toBeNull(); // window [1,2,null]
    expect(sma3[3]).toBeNull(); // window [2,null,4]
    expect(sma3[4]).toBeNull(); // window [null,4,5]
  });
});

describe("computeReturnsTable", () => {
  const bars = [
    { date: "2023-09-26", close: 100 },
    { date: "2024-09-26", close: 110 },
    { date: "2025-09-26", close: 121 },
    { date: "2026-09-26", close: 133.1 },
  ];

  it("computes 1Y return and CAGR from the closest available start point", () => {
    const table = computeReturnsTable(bars, [{ label: "1Y", days: 365 }]);
    expect(table[0].returnPct).toBeCloseTo(10.0, 1);
    expect(table[0].cagrPct).toBeCloseTo(10.0, 1);
  });

  it("returns null for a span longer than the available history, not a truncated guess", () => {
    const table = computeReturnsTable(bars, [{ label: "10Y", days: 3650 }]);
    expect(table[0].returnPct).toBeNull();
  });

  it("does not compute a CAGR for a sub-1-year span", () => {
    const table = computeReturnsTable(bars, [{ label: "1M", days: 30 }]);
    expect(table[0].cagrPct).toBeNull();
  });

  it("empty bars returns all-null rows", () => {
    const table = computeReturnsTable([], [{ label: "1Y", days: 365 }]);
    expect(table[0]).toEqual({ label: "1Y", returnPct: null, cagrPct: null });
  });
});

describe("alignByDate", () => {
  it("pairs same-length series unchanged when every date matches", () => {
    const a = [
      { date: "2026-01-01", close: 100 },
      { date: "2026-01-02", close: 101 },
    ];
    const b = [
      { date: "2026-01-01", close: 200 },
      { date: "2026-01-02", close: 202 },
    ];
    expect(alignByDate(a, b)).toEqual({
      dates: ["2026-01-01", "2026-01-02"],
      a: [100, 101],
      b: [200, 202],
    });
  });

  it("does not let one series' missing date shift the other series' values", () => {
    // `b` is missing 2026-01-02 (its own null-close/gap day) -- this used
    // to be simulated by index-pairing two independently-built arrays,
    // which would silently compare a's 2026-01-03 value against b's
    // 2026-01-02 value. Aligning by date keeps them apart as a gap instead.
    const a = [
      { date: "2026-01-01", close: 100 },
      { date: "2026-01-02", close: 101 },
      { date: "2026-01-03", close: 102 },
    ];
    const b = [
      { date: "2026-01-01", close: 200 },
      { date: "2026-01-03", close: 203 },
    ];
    const aligned = alignByDate(a, b);
    expect(aligned.dates).toEqual(["2026-01-01", "2026-01-02", "2026-01-03"]);
    expect(aligned.a).toEqual([100, 101, 102]);
    expect(aligned.b).toEqual([200, null, 203]); // gap, not 202-shifted-in
  });

  it("truncates the date portion of a full ISO timestamp before comparing", () => {
    const a = [{ date: "2026-01-01T09:15:00.000Z", close: 100 }];
    const b = [{ date: "2026-01-01", close: 200 }];
    const aligned = alignByDate(a, b);
    expect(aligned.dates).toEqual(["2026-01-01"]);
    expect(aligned.a).toEqual([100]);
    expect(aligned.b).toEqual([200]);
  });
});
