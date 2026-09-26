"use client";

import { useState } from "react";
import * as Popover from "@radix-ui/react-popover";
import { Command, CommandGroup, CommandInput, CommandItem, CommandList, CommandEmpty } from "@/components/ui/command";
import { ChevronsUpDown } from "lucide-react";
import { cn } from "@/lib/utils";
import { changeDirection, changeGlyph, formatPercent } from "@/lib/format";
import { useQuotes } from "@/lib/queries";
import type { CompanyRef } from "@/lib/api";

export function CompanyCombobox({
  companies,
  value,
  onChange,
}: {
  companies: CompanyRef[];
  value: string | null;
  onChange: (symbol: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const symbols = companies.map((c) => c.symbol);
  const { data: quotes } = useQuotes(symbols);
  const quoteBySymbol = new Map((quotes ?? []).map((q) => [q.symbol, q]));

  const selected = companies.find((c) => c.symbol === value) ?? null;

  return (
    <Popover.Root open={open} onOpenChange={setOpen}>
      <Popover.Trigger asChild>
        <button
          role="combobox"
          aria-expanded={open}
          aria-controls="company-combobox-list"
          aria-label="Select company"
          className="flex h-9 min-w-56 items-center justify-between gap-2 rounded-md border border-border bg-surface px-3 text-sm hover:bg-surface-raised"
        >
          <span className="flex items-center gap-2 truncate">
            {selected ? (
              <>
                <CompanyAvatar name={selected.name} />
                <span className="truncate">{selected.name}</span>
                <span className="text-muted">{selected.symbol}</span>
              </>
            ) : (
              "Select company…"
            )}
          </span>
          <ChevronsUpDown size={14} className="shrink-0 text-muted" />
        </button>
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content
          id="company-combobox-list"
          align="start"
          sideOffset={4}
          className="z-50 w-80 rounded-md border border-border bg-surface-raised shadow-lg"
        >
          <Command>
            <CommandInput placeholder="Search companies…" />
            <CommandList>
              <CommandEmpty>No company found.</CommandEmpty>
              <CommandGroup>
                {companies.map((company) => {
                  const quote = quoteBySymbol.get(company.symbol);
                  const direction = changeDirection(quote?.change_pct);
                  return (
                    <CommandItem
                      key={company.symbol}
                      value={`${company.symbol} ${company.name}`}
                      onSelect={() => {
                        onChange(company.symbol);
                        setOpen(false);
                      }}
                      className={cn(value === company.symbol && "bg-accent/10 text-accent")}
                    >
                      <CompanyAvatar name={company.name} />
                      <span className="flex-1 truncate">{company.name}</span>
                      <span className="text-xs text-muted">{company.symbol}</span>
                      {quote && (
                        <span
                          className={cn(
                            "w-16 shrink-0 text-right text-xs tabular-nums-fixed",
                            direction === "up" && "text-up",
                            direction === "down" && "text-down",
                            direction === "flat" && "text-muted"
                          )}
                        >
                          {changeGlyph(quote.change_pct)} {formatPercent(quote.change_pct, 1)}
                        </span>
                      )}
                    </CommandItem>
                  );
                })}
              </CommandGroup>
            </CommandList>
          </Command>
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}

export function CompanyAvatar({ name }: { name: string }) {
  const initial = name.trim().charAt(0).toUpperCase() || "?";
  return (
    <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-accent/20 text-[11px] font-semibold text-accent">
      {initial}
    </span>
  );
}
