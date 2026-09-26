"use client";

import { useEffect, useRef, useState } from "react";

export type FlashDirection = "up" | "down" | null;

/** Briefly flags a value change so a component can flash green/red --
 * value going up flashes "up", down flashes "down", first render and
 * ties flash nothing. */
export function useFlashOnChange(value: number | null | undefined): FlashDirection {
  const previous = useRef<number | null | undefined>(value);
  const [flash, setFlash] = useState<FlashDirection>(null);

  useEffect(() => {
    if (value === undefined || value === null || previous.current === value) {
      previous.current = value;
      return;
    }
    if (previous.current !== null && previous.current !== undefined) {
      const direction: FlashDirection = value > previous.current ? "up" : "down";
      setFlash(direction);
      const timeout = setTimeout(() => setFlash(null), 900);
      previous.current = value;
      return () => clearTimeout(timeout);
    }
    previous.current = value;
  }, [value]);

  return flash;
}
