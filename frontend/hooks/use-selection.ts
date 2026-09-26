"use client";

import { useCallback, useEffect, useMemo } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useUniverse, useQuotes } from "@/lib/queries";
import { useSelectionStore } from "@/lib/store";
import type { CompanyRef } from "@/lib/api";

/**
 * The URL (?sector=...&symbol=...) is the source of truth for the current
 * selection (task 3.4) -- this hook resolves it against the loaded
 * universe, auto-selecting the largest-market-cap company whenever the
 * sector changes and no symbol is (yet) in the URL, and keeps the Zustand
 * store (lib/store.ts) mirrored for components that don't want to read the
 * URL directly.
 */
export function useSelection() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const universeQuery = useUniverse();
  const setStoreSector = useSelectionStore((s) => s.setSector);
  const setStoreSymbol = useSelectionStore((s) => s.setSymbol);

  const sectors = useMemo(() => universeQuery.data?.sectors ?? [], [universeQuery.data]);
  const urlSector = searchParams.get("sector");
  const urlSymbol = searchParams.get("symbol");

  const currentSectorName = urlSector ?? sectors[0]?.name ?? null;
  const currentSectorGroup = useMemo(
    () => sectors.find((s) => s.name === currentSectorName) ?? null,
    [sectors, currentSectorName]
  );

  const sectorSymbols = useMemo(
    () => currentSectorGroup?.companies.map((c) => c.symbol) ?? [],
    [currentSectorGroup]
  );
  const sectorQuotesQuery = useQuotes(sectorSymbols);

  const largestCompanyInSector = useMemo(() => {
    if (!sectorQuotesQuery.data || sectorQuotesQuery.data.length === 0) return null;
    let best = sectorQuotesQuery.data[0];
    for (const quote of sectorQuotesQuery.data) {
      if ((quote.market_cap ?? 0) > (best.market_cap ?? 0)) best = quote;
    }
    return best.symbol;
  }, [sectorQuotesQuery.data]);

  const currentSymbol = urlSymbol ?? largestCompanyInSector;

  const currentCompany: CompanyRef | null = useMemo(
    () => currentSectorGroup?.companies.find((c) => c.symbol === currentSymbol) ?? null,
    [currentSectorGroup, currentSymbol]
  );

  const navigate = useCallback(
    (sector: string, symbol: string | null, mode: "push" | "replace" = "push") => {
      const params = new URLSearchParams(searchParams.toString());
      params.set("sector", sector);
      if (symbol) {
        params.set("symbol", symbol);
      } else {
        params.delete("symbol");
      }
      const url = `${pathname}?${params.toString()}`;
      if (mode === "replace") {
        router.replace(url, { scroll: false });
      } else {
        router.push(url, { scroll: false });
      }
    },
    [router, pathname, searchParams]
  );

  // Once we've resolved a default sector/symbol (nothing was in the URL
  // yet, or the sector changed and we just found its largest company),
  // write it back into the URL so the view is immediately shareable.
  useEffect(() => {
    if (!currentSectorName) return;
    if (urlSector === currentSectorName && urlSymbol) return;
    if (!currentSymbol) return;
    navigate(currentSectorName, currentSymbol, "replace");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentSectorName, currentSymbol, urlSector, urlSymbol]);

  useEffect(() => {
    setStoreSector(currentSectorName);
  }, [currentSectorName, setStoreSector]);

  useEffect(() => {
    setStoreSymbol(currentSymbol ?? null);
  }, [currentSymbol, setStoreSymbol]);

  const selectSector = useCallback(
    (sector: string) => {
      // Clear the symbol -- the effect above fills in that sector's
      // largest company once its quotes load.
      navigate(sector, null);
    },
    [navigate]
  );

  const selectSymbol = useCallback(
    (symbol: string) => {
      if (!currentSectorName) return;
      navigate(currentSectorName, symbol);
    },
    [currentSectorName, navigate]
  );

  /** Select a company by symbol regardless of which sector it's in (⌘K search). */
  const selectSymbolAnySector = useCallback(
    (symbol: string) => {
      const sector = sectors.find((s) => s.companies.some((c) => c.symbol === symbol));
      if (sector) navigate(sector.name, symbol);
    },
    [sectors, navigate]
  );

  return {
    sectors,
    isLoading: universeQuery.isLoading,
    currentSectorName,
    currentSectorGroup,
    currentSymbol,
    currentCompany,
    selectSector,
    selectSymbol,
    selectSymbolAnySector,
  };
}
