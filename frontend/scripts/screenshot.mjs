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

      // Wait for the Overview tab's slowest-loading piece (the health
      // radar needs /api/ratios, which itself needs every sector peer's
      // financials) rather than just the header, so charts are fully
      // rendered before the screenshot.
      await page.getByText("Financial health radar").waitFor({ timeout: 30000 });
      await page.getByText("Key stats").waitFor({ timeout: 30000 });
      await page.waitForTimeout(800); // let chart animations/price-flash settle

      const filename = `${target.symbol}_${viewport.name}_${theme}.png`;
      await page.screenshot({ path: path.join(outDir, filename), fullPage: true });
      console.log("Saved", filename);
    }

    await context.close();
  }
}

await browser.close();
