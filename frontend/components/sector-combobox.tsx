"use client";

import { useState } from "react";
import * as Popover from "@radix-ui/react-popover";
import { Command, CommandGroup, CommandInput, CommandItem, CommandList } from "@/components/ui/command";
import { ChevronsUpDown } from "lucide-react";
import { cn } from "@/lib/utils";
import type { SectorGroup } from "@/lib/api";

export function SectorCombobox({
  sectors,
  value,
  onChange,
}: {
  sectors: SectorGroup[];
  value: string | null;
  onChange: (sector: string) => void;
}) {
  const [open, setOpen] = useState(false);

  return (
    <Popover.Root open={open} onOpenChange={setOpen}>
      <Popover.Trigger asChild>
        <button
          role="combobox"
          aria-expanded={open}
          aria-controls="sector-combobox-list"
          aria-label="Select sector"
          className="flex h-9 min-w-48 items-center justify-between gap-2 rounded-md border border-border bg-surface px-3 text-sm hover:bg-surface-raised"
        >
          <span className="truncate">{value ?? "Select sector…"}</span>
          <ChevronsUpDown size={14} className="shrink-0 text-muted" />
        </button>
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content
          id="sector-combobox-list"
          align="start"
          sideOffset={4}
          className="z-50 w-72 rounded-md border border-border bg-surface-raised shadow-lg"
        >
          <Command>
            <CommandInput placeholder="Search sectors…" />
            <CommandList>
              <CommandGroup>
                {sectors.map((sector) => (
                  <CommandItem
                    key={sector.name}
                    value={sector.name}
                    onSelect={() => {
                      onChange(sector.name);
                      setOpen(false);
                    }}
                    className={cn(value === sector.name && "bg-accent/10 text-accent")}
                  >
                    <span className="truncate">{sector.name}</span>
                    <span className="ml-auto text-xs text-muted">{sector.companies.length}</span>
                  </CommandItem>
                ))}
              </CommandGroup>
            </CommandList>
          </Command>
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}
