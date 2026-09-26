"use client";

import { useSelectionStore } from "@/lib/store";
import { cn } from "@/lib/utils";

const OPTIONS = [
  { value: "crore" as const, label: "₹ Cr" },
  { value: "lakh_crore" as const, label: "₹ L Cr" },
];

export function UnitsToggle() {
  const unit = useSelectionStore((s) => s.unit);
  const setUnit = useSelectionStore((s) => s.setUnit);

  return (
    <div className="inline-flex rounded-md border border-border p-0.5 text-xs" role="group" aria-label="Currency unit">
      {OPTIONS.map((option) => (
        <button
          key={option.value}
          onClick={() => setUnit(option.value)}
          aria-pressed={unit === option.value}
          className={cn(
            "rounded px-2 py-1 tabular-nums-fixed transition-colors",
            unit === option.value ? "bg-accent text-accent-foreground" : "text-muted hover:text-foreground"
          )}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}
