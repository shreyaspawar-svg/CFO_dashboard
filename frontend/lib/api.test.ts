import { describe, expect, it, vi, beforeEach } from "vitest";
import { api } from "./api";

describe("api.quotes URL encoding", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({ ok: true, json: async () => [] }))
    );
  });

  it("URL-encodes symbols containing '&' (e.g. M&M), so it can't be split into a stray query param", async () => {
    await api.quotes(["TCS", "M&M", "RELIANCE"]);
    const calledUrl = (fetch as unknown as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    expect(calledUrl).toContain("M%26M");
    expect(calledUrl).not.toMatch(/symbols=TCS,M(?!%)/); // not truncated at the bare "&"
  });

  it("URL-encodes a single symbol in a path segment the same way", async () => {
    await api.quote("M&M");
    const calledUrl = (fetch as unknown as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    expect(calledUrl).toBe("/api/quote/M%26M");
  });
});
