import { describe, expect, it } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useFlashOnChange } from "./use-flash-on-change";

describe("useFlashOnChange", () => {
  it("does not flash on first render", () => {
    const { result } = renderHook(({ value }) => useFlashOnChange(value), {
      initialProps: { value: 100 },
    });
    expect(result.current).toBeNull();
  });

  it("flashes up when the value increases", () => {
    const { result, rerender } = renderHook(({ value }) => useFlashOnChange(value), {
      initialProps: { value: 100 },
    });
    rerender({ value: 105 });
    expect(result.current).toBe("up");
  });

  it("flashes down when the value decreases", () => {
    const { result, rerender } = renderHook(({ value }) => useFlashOnChange(value), {
      initialProps: { value: 100 },
    });
    rerender({ value: 95 });
    expect(result.current).toBe("down");
  });

  it("does not flash when the value is unchanged", () => {
    const { result, rerender } = renderHook(({ value }) => useFlashOnChange(value), {
      initialProps: { value: 100 },
    });
    rerender({ value: 100 });
    expect(result.current).toBeNull();
  });

  it("clears the flash after the timeout", async () => {
    const { result, rerender } = renderHook(({ value }) => useFlashOnChange(value), {
      initialProps: { value: 100 },
    });
    rerender({ value: 105 });
    expect(result.current).toBe("up");
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 950));
    });
    expect(result.current).toBeNull();
  });
});
