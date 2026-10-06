"use client";

import { useEffect } from "react";
import { useSelectionStore } from "@/lib/store";
import type { CompanyRef } from "@/lib/api";

/**
 * This dashboard is scoped to a single company (Reliance Industries) --
 * see PLAN.md's RIL single-company pivot. This used to resolve a company
 * from the full 50-company universe via `?sector=&symbol=` URL params
 * (sector/company comboboxes, ⌘K search); that selection UI is gone, so
 * this now just returns the fixed company below. Kept as a hook (not
 * inlined into dashboard-shell.tsx) so a future multi-company mode only
 * needs to change this one file, and so lib/store.ts's sector/symbol
 * mirror -- read by nothing today, but cheap to keep correct -- still
 * reflects the active company.
 */
const RELIANCE: CompanyRef = {
  symbol: "RELIANCE",
  yf_ticker: "RELIANCE.NS",
  name: "Reliance Industries Ltd",
  template: "general",
};
const RELIANCE_SECTOR = "Oil, Gas & Energy";

export function useSelection() {
  const setStoreSector = useSelectionStore((s) => s.setSector);
  const setStoreSymbol = useSelectionStore((s) => s.setSymbol);

  useEffect(() => {
    setStoreSector(RELIANCE_SECTOR);
    setStoreSymbol(RELIANCE.symbol);
  }, [setStoreSector, setStoreSymbol]);

  return {
    isLoading: false,
    currentSectorName: RELIANCE_SECTOR,
    currentCompany: RELIANCE,
  };
}
