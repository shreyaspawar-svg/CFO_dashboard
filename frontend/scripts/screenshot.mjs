import { chromium } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const outDir = path.join(__dirname, "..", "screenshots");

const TARGETS = [
  { symbol: "TCS", sector: "Information Technology" },
  { symbol: "HDFCBANK", sector: "Banks & Financial Services" },
  { symbol: "TMPV", sector: "Automobiles" },
];
const VIEWPORTS = [
  { name: "desktop", width: 1440, height: 900 },
  { name: "mobile", width: 390, height: 844 },
];
const THEMES = ["dark", "light"];

const browser = await chromium.launch();

for (const theme of THEMES) {
  for (const viewport of VIEWPORTS) {
    const context = await browser.newContext({
      viewport: { width: viewport.width, height: viewport.height },
      colorScheme: theme,
    });
    const page = await context.newPage();

    for (const target of TARGETS) {
      const url = `http://localhost:3000/?sector=${encodeURIComponent(target.sector)}&symbol=${target.symbol}`;
      await page.goto(url);

      // Force the theme via the toggle rather than relying on colorScheme
      // alone, since our ThemeProvider persists to localStorage per-origin
      // and defaults to dark regardless of prefers-color-scheme.
      const isLight = await page.evaluate(() => document.documentElement.getAttribute("data-theme") === "light");
      if ((theme === "light") !== isLight) {
        await page.getByRole("button", { name: "Toggle theme" }).click();
      }

      // Wait for the company header to actually resolve (live quote data),
      // not just the shell chrome.
      await page.getByText(new RegExp(target.symbol)).first().waitFor({ timeout: 20000 });
      await page.waitForTimeout(500); // let any price-flash animation settle

      const filename = `${target.symbol}_${viewport.name}_${theme}.png`;
      await page.screenshot({ path: path.join(outDir, filename), fullPage: true });
      console.log("Saved", filename);
    }

    await context.close();
  }
}

await browser.close();
