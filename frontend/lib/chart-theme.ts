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
  foreground: "#f3ecdd",
  muted: "#a0a8bf",
  border: "#3c4c72",
  accent: "#e0798c",
  up: "#6fbf95",
  down: "#e0798c",
  series: ["#e0798c", "#d8bd82", "#8ea9c9", "#6fbf95", "#c9a0dc"],
};

export const LIGHT_CHART_THEME: ChartTheme = {
  background: "transparent",
  foreground: "#1b2942",
  muted: "#756c58",
  border: "#d8c9a3",
  accent: "#8a2a3b",
  up: "#2f6f4f",
  down: "#8a2a3b",
  series: ["#8a2a3b", "#6b4a10", "#3c5a80", "#2f6f4f", "#8b5fa3"],
};

export function chartThemeFor(theme: string | undefined): ChartTheme {
  return theme === "light" ? LIGHT_CHART_THEME : DARK_CHART_THEME;
}
