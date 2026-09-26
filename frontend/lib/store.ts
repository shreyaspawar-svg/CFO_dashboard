import { create } from "zustand";
import type { Unit } from "@/lib/format";

interface SelectionState {
  sector: string | null;
  symbol: string | null;
  unit: Unit;
  period: "annual" | "quarterly";
  setSector: (sector: string | null) => void;
  setSymbol: (symbol: string | null) => void;
  setUnit: (unit: Unit) => void;
  setPeriod: (period: "annual" | "quarterly") => void;
}

/**
 * Selection state. The URL (?sector=...&symbol=...) is the source of truth
 * for sector/symbol -- components read the URL via useSearchParams and call
 * these setters to keep this store in sync for components that can't
 * conveniently read the URL themselves (e.g. deeply nested KPI cards).
 * Never write sector/symbol here first and expect the URL to follow; see
 * hooks/use-selection.ts for the URL <-> store sync.
 */
export const useSelectionStore = create<SelectionState>((set) => ({
  sector: null,
  symbol: null,
  unit: "crore",
  period: "annual",
  setSector: (sector) => set({ sector }),
  setSymbol: (symbol) => set({ symbol }),
  setUnit: (unit) => set({ unit }),
  setPeriod: (period) => set({ period }),
}));
