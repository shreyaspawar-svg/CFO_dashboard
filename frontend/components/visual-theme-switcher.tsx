"use client";

// UI-exploration branch only -- remove before merging to main (see
// lib/visual-theme.tsx).

import { useEffect, useState } from "react";
import { useVisualTheme, VISUAL_THEMES, type VisualTheme } from "@/lib/visual-theme";

export function VisualThemeSwitcher() {
  const { visualTheme, setVisualTheme } = useVisualTheme();
  // Same hydration-mismatch guard as ThemeToggle: the server always
  // renders the default ("terminal") since localStorage isn't available
  // yet during SSR.
  const [mounted, setMounted] = useState(false);
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setMounted(true);
  }, []);

  return (
    <select
      value={mounted ? visualTheme : "terminal"}
      onChange={(e) => setVisualTheme(e.target.value as VisualTheme)}
      aria-label="UI theme (exploration)"
      className="rounded-md border border-border bg-surface px-2 py-1 text-xs text-foreground"
    >
      {VISUAL_THEMES.map((t) => (
        <option key={t.value} value={t.value}>
          {t.label}
        </option>
      ))}
    </select>
  );
}
