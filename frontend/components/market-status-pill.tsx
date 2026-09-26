"use client";

import { useEffect, useState } from "react";
import { marketStatus, type MarketStatus } from "@/lib/market-status";
import { cn } from "@/lib/utils";

const LABELS: Record<MarketStatus, string> = {
  open: "Open",
  closed: "Closed",
  pre_open: "Pre-open",
};

const DOT_CLASSES: Record<MarketStatus, string> = {
  open: "bg-up",
  closed: "bg-muted",
  pre_open: "bg-warning-foreground",
};

export function MarketStatusPill() {
  const [status, setStatus] = useState<MarketStatus>("closed");

  useEffect(() => {
    // Client-only: the server doesn't know the viewer's clock, and this
    // needs to re-check every minute, not just once on mount.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setStatus(marketStatus());
    const id = setInterval(() => setStatus(marketStatus()), 60_000);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="inline-flex items-center gap-1.5 rounded-full border border-border px-2.5 py-1 text-xs">
      <span className={cn("h-1.5 w-1.5 rounded-full", DOT_CLASSES[status])} aria-hidden />
      <span>{LABELS[status]}</span>
    </div>
  );
}
