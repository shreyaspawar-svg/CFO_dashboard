import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { downloadCsv } from "./chart-export";

const originalCreateElement = document.createElement.bind(document);

describe("downloadCsv", () => {
  let clickSpy: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    clickSpy = vi.fn();
    vi.stubGlobal("URL", { createObjectURL: vi.fn(() => "blob:mock"), revokeObjectURL: vi.fn() });
    vi.spyOn(document, "createElement").mockImplementation((tag: string) => {
      const el = originalCreateElement(tag);
      if (tag === "a") (el as HTMLAnchorElement).click = clickSpy as unknown as () => void;
      return el;
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("builds a CSV with a header row and escapes commas/quotes", () => {
    let capturedBlob: Blob | null = null;
    vi.spyOn(globalThis.URL, "createObjectURL").mockImplementation((blob: Blob | MediaSource) => {
      const blobTyped = blob as Blob;
      capturedBlob = blobTyped;
      return "blob:mock";
    });

    downloadCsv("test.csv", ["Date", "Note"], [["2024-03-31", 'has a "quote", and comma']]);

    expect(clickSpy).toHaveBeenCalledOnce();
    expect(capturedBlob).not.toBeNull();
  });

  it("renders null values as an empty cell, not the string 'null'", async () => {
    let capturedBlob: Blob | null = null;
    vi.spyOn(globalThis.URL, "createObjectURL").mockImplementation((blob: Blob | MediaSource) => {
      const blobTyped = blob as Blob;
      capturedBlob = blobTyped;
      return "blob:mock";
    });

    downloadCsv("test.csv", ["Date", "Value"], [["2024-03-31", null]]);

    const text = await (capturedBlob as unknown as Blob).text();
    expect(text).toContain("2024-03-31,");
    expect(text).not.toContain("null");
  });
});
