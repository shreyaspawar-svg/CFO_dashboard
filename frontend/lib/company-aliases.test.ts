import { describe, expect, it } from "vitest";
import { matchesSearch } from "./company-aliases";

describe("matchesSearch", () => {
  it("finds ETERNAL when searching for its former name Zomato", () => {
    expect(matchesSearch("ETERNAL", "Eternal Ltd", "zomato")).toBe(true);
  });

  it("finds TMPV when searching for Tata Motors", () => {
    expect(matchesSearch("TMPV", "Tata Motors Passenger Vehicles Ltd", "tata motors")).toBe(true);
  });

  it("still matches on symbol and current name directly", () => {
    expect(matchesSearch("TCS", "Tata Consultancy Services Ltd", "TCS")).toBe(true);
    expect(matchesSearch("TCS", "Tata Consultancy Services Ltd", "consultancy")).toBe(true);
  });

  it("is case-insensitive", () => {
    expect(matchesSearch("ETERNAL", "Eternal Ltd", "ZOMATO")).toBe(true);
  });

  it("does not match unrelated queries", () => {
    expect(matchesSearch("TCS", "Tata Consultancy Services Ltd", "infosys")).toBe(false);
  });

  it("empty query matches everything", () => {
    expect(matchesSearch("TCS", "Tata Consultancy Services Ltd", "")).toBe(true);
  });
});
