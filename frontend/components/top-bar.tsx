"use client";

import { useSelection } from "@/hooks/use-selection";
import { SectorCombobox } from "@/components/sector-combobox";
import { CompanyCombobox } from "@/components/company-combobox";
import { CommandSearch } from "@/components/command-search";
import { MarketStatusPill } from "@/components/market-status-pill";
import { UnitsToggle } from "@/components/units-toggle";
import { ThemeToggle } from "@/components/theme-toggle";
import { TickerTape } from "@/components/ticker-tape";

export function TopBar() {
  const { sectors, currentSectorName, currentSectorGroup, currentSymbol, selectSector, selectSymbol } =
    useSelection();

  return (
    <div className="sticky top-0 z-40 border-b border-border bg-background/95 backdrop-blur">
      <div className="flex flex-wrap items-center gap-3 px-4 py-3">
        <span className="brand-title mr-2 text-sm font-semibold tracking-tight">CFO Dashboard</span>

        <SectorCombobox sectors={sectors} value={currentSectorName} onChange={selectSector} />
        <CompanyCombobox
          companies={currentSectorGroup?.companies ?? []}
          value={currentSymbol}
          onChange={selectSymbol}
        />

        <div className="flex-1" />

        <CommandSearch />
        <MarketStatusPill />
        <UnitsToggle />
        <ThemeToggle />
      </div>
      <TickerTape />
    </div>
  );
}
