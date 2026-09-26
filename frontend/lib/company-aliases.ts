/**
 * Common/former names for companies whose current NSE symbol or listed
 * name wouldn't otherwise surface in a fuzzy search -- "Zomato" must find
 * ETERNAL (renamed 2024), "Tata Motors" must find TMPV (demerged into the
 * passenger-vehicle entity in 2025; see backend/data/corporate_actions.json
 * for why). Neither is derivable from the API alone, so this is a small
 * hand-maintained table, mirroring the backend's own corporate-actions
 * approach to undocumented-by-the-data-source history.
 */
export const COMPANY_ALIASES: Record<string, string[]> = {
  ETERNAL: ["zomato"],
  TMPV: ["tata motors", "tata motors passenger vehicles"],
  JIOFIN: ["jio financial", "reliance strategic investments"],
};

/** All search text for a symbol: its own name/symbol plus any aliases. */
export function searchTermsFor(symbol: string, name: string): string[] {
  return [symbol, name, ...(COMPANY_ALIASES[symbol] ?? [])];
}

/** True if `query` matches the symbol, its listed name, or a known alias. */
export function matchesSearch(symbol: string, name: string, query: string): boolean {
  const needle = query.trim().toLowerCase();
  if (!needle) return true;
  return searchTermsFor(symbol, name).some((term) => term.toLowerCase().includes(needle));
}
