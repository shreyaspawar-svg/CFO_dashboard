"use client";

import { useEffect, useMemo, useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { VisuallyHidden } from "@radix-ui/react-visually-hidden";
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from "@/components/ui/command";
import { CompanyAvatar } from "@/components/company-combobox";
import { matchesSearch } from "@/lib/company-aliases";
import { useSelection } from "@/hooks/use-selection";

export function CommandSearch() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const { sectors, selectSymbolAnySector } = useSelection();

  const allCompanies = useMemo(
    () => sectors.flatMap((s) => s.companies.map((c) => ({ ...c, sectorName: s.name }))),
    [sectors]
  );

  const filtered = useMemo(
    () => allCompanies.filter((c) => matchesSearch(c.symbol, c.name, query)),
    [allCompanies, query]
  );

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setOpen((v) => !v);
      }
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, []);

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="flex h-9 items-center gap-2 rounded-md border border-border bg-surface px-3 text-sm text-muted hover:bg-surface-raised"
      >
        <span>Search companies…</span>
        <kbd className="rounded border border-border bg-surface px-1.5 py-0.5 text-[10px]">⌘K</kbd>
      </button>
      <Dialog.Root open={open} onOpenChange={setOpen}>
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 z-50 bg-black/50" />
          <Dialog.Content className="fixed left-1/2 top-24 z-50 w-full max-w-lg -translate-x-1/2 rounded-lg border border-border bg-surface-raised shadow-2xl">
            <VisuallyHidden>
              <Dialog.Title>Search companies</Dialog.Title>
              <Dialog.Description>
                Search all 50 NIFTY companies by symbol, name, or former/common name
              </Dialog.Description>
            </VisuallyHidden>
            <Command shouldFilter={false}>
              <CommandInput
                autoFocus
                placeholder="Search by name, symbol, or e.g. “Zomato”, “Tata Motors”…"
                value={query}
                onValueChange={setQuery}
              />
              <CommandList>
                <CommandEmpty>No company found.</CommandEmpty>
                <CommandGroup>
                  {filtered.slice(0, 20).map((company) => (
                    <CommandItem
                      key={company.symbol}
                      value={company.symbol}
                      onSelect={() => {
                        selectSymbolAnySector(company.symbol);
                        setOpen(false);
                        setQuery("");
                      }}
                    >
                      <CompanyAvatar name={company.name} />
                      <span className="flex-1 truncate">{company.name}</span>
                      <span className="text-xs text-muted">{company.symbol}</span>
                    </CommandItem>
                  ))}
                </CommandGroup>
              </CommandList>
            </Command>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </>
  );
}
