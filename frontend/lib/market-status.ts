/**
 * NSE market-hours check (IST, weekdays, 09:15-15:30, pre-open from 09:00).
 * Mirrors backend/app/services/market.py exactly -- an NSE holiday
 * calendar is out of scope for both sides (documented there), so a
 * holiday simply shows as "closed", same as a weekend.
 */
export type MarketStatus = "open" | "closed" | "pre_open";

const IST_OFFSET_MINUTES = 5 * 60 + 30;

export function marketStatus(now: Date = new Date()): MarketStatus {
  const istMillis = now.getTime() + IST_OFFSET_MINUTES * 60 * 1000;
  const ist = new Date(istMillis);
  const day = ist.getUTCDay(); // 0=Sun .. 6=Sat, in the shifted "IST-as-UTC" clock
  if (day === 0 || day === 6) return "closed";

  const minutesSinceMidnight = ist.getUTCHours() * 60 + ist.getUTCMinutes();
  const preOpenStart = 9 * 60;
  const marketOpen = 9 * 60 + 15;
  const marketClose = 15 * 60 + 30;

  if (minutesSinceMidnight >= preOpenStart && minutesSinceMidnight < marketOpen) return "pre_open";
  if (minutesSinceMidnight >= marketOpen && minutesSinceMidnight <= marketClose) return "open";
  return "closed";
}
