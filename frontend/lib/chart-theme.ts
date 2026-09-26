/**
 * One shared ECharts colour theme for dark and light mode (Phase 4 §4.0
 * chart foundation) -- mirrors the CSS custom properties in
 * app/globals.css exactly, so a chart never looks like a different app
 * from the page it sits in. Keep the two in sync if either changes.
 */

export interface ChartTheme {
  background: string;
  foreground: string;
  muted: string;
  border: string;
  accent: string;
  up: string;
  down: string;
  series: string[];
}

export const DARK_CHART_THEME: ChartTheme = {
  background: "transparent",
  foreground: "#e8eaed",
  muted: "#8b93a1",
  border: "#262b33",
  accent: "#4f8dfd",
  up: "#1fb15a",
  down: "#e5484d",
  series: ["#4f8dfd", "#f5c257", "#a78bfa", "#34d1c8", "#f472b6"],
};

export const LIGHT_CHART_THEME: ChartTheme = {
  background: "transparent",
  foreground: "#14171c",
  muted: "#5b6472",
  border: "#e2e5ea",
  accent: "#2563eb",
  up: "#16813b",
  down: "#c9302c",
  series: ["#2563eb", "#b8860b", "#7c3aed", "#0d9488", "#db2777"],
};

export function chartThemeFor(theme: string | undefined): ChartTheme {
  return theme === "light" ? LIGHT_CHART_THEME : DARK_CHART_THEME;
}
