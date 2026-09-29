"use client";

/**
 * UI-exploration branch only: a second, independent theme axis (visual
 * language) alongside next-themes' existing dark/light axis. Deliberately
 * NOT built on next-themes -- that library models one theme dimension,
 * and combining a second one into its `themes` list would mean every
 * combination needs its own name (e.g. "editorial-dark"). A separate
 * `data-visual-theme` attribute keeps it orthogonal to `data-theme`
 * (dark/light), so CSS can key off both independently
 * (`:root[data-visual-theme="editorial"][data-theme="dark"]`).
 *
 * Remove this file and its usages before merging to main -- this switcher
 * exists only for side-by-side comparison on this branch.
 */

import { createContext, useContext, useEffect, useState } from "react";

export type VisualTheme = "terminal" | "clean-saas" | "editorial";

export const VISUAL_THEMES: { value: VisualTheme; label: string }[] = [
  { value: "terminal", label: "Terminal" },
  { value: "clean-saas", label: "Clean SaaS" },
  { value: "editorial", label: "Editorial" },
];

const STORAGE_KEY = "ui-exploration-visual-theme";

const VisualThemeContext = createContext<{
  visualTheme: VisualTheme;
  setVisualTheme: (theme: VisualTheme) => void;
} | null>(null);

function isVisualTheme(value: string | null): value is VisualTheme {
  return value != null && VISUAL_THEMES.some((t) => t.value === value);
}

export function VisualThemeProvider({ children }: { children: React.ReactNode }) {
  const [visualTheme, setVisualThemeState] = useState<VisualTheme>("terminal");

  useEffect(() => {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (isVisualTheme(stored)) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setVisualThemeState(stored);
    }
  }, []);

  useEffect(() => {
    document.documentElement.setAttribute("data-visual-theme", visualTheme);
  }, [visualTheme]);

  const setVisualTheme = (theme: VisualTheme) => {
    setVisualThemeState(theme);
    window.localStorage.setItem(STORAGE_KEY, theme);
  };

  return (
    <VisualThemeContext.Provider value={{ visualTheme, setVisualTheme }}>{children}</VisualThemeContext.Provider>
  );
}

export function useVisualTheme() {
  const ctx = useContext(VisualThemeContext);
  if (!ctx) throw new Error("useVisualTheme must be used within VisualThemeProvider");
  return ctx;
}
