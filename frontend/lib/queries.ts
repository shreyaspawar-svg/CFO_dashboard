import { useQuery, type Query } from "@tanstack/react-query";
import { api, type QuoteResponse } from "@/lib/api";

// staleTime values mirror the backend's own cache TTLs (see
// backend/app/config.py) so the frontend doesn't poll faster than the data
// actually changes.
const STALE_TIME = {
  universe: 24 * 60 * 60 * 1000,
  quote: 30 * 1000,
  history: 6 * 60 * 60 * 1000,
  financials: 12 * 60 * 60 * 1000,
  ratios: 12 * 60 * 60 * 1000,
  peers: 60 * 60 * 1000,
  valuation: 6 * 60 * 60 * 1000,
  events: 6 * 60 * 60 * 1000,
  glossary: 24 * 60 * 60 * 1000,
  kpiScorecard: 12 * 60 * 60 * 1000,
} as const;

// Live-price polling (PLAN.md Phase 5 §B.1): only poll while the BACKEND's
// own market_status (not the viewer's clock) says the market is open, and
// only at these intervals -- React Query's `refetchIntervalInBackground`
// defaults to false, so this already pauses on its own the moment the
// browser tab is hidden, with no extra code needed here.
const QUOTE_POLL_MS = 15_000;
const BATCH_POLL_MS = 60_000;

function marketIsOpen(quote: QuoteResponse | null | undefined): boolean {
  return quote?.market_status === "open";
}

export function useUniverse() {
  return useQuery({
    queryKey: ["universe"],
    queryFn: api.universe,
    staleTime: STALE_TIME.universe,
  });
}

export function useQuote(symbol: string | null) {
  return useQuery({
    queryKey: ["quote", symbol],
    queryFn: () => api.quote(symbol as string),
    enabled: !!symbol,
    staleTime: STALE_TIME.quote,
    refetchInterval: (query: Query<QuoteResponse>) => (marketIsOpen(query.state.data) ? QUOTE_POLL_MS : false),
  });
}

export function useQuotes(symbols: string[]) {
  return useQuery({
    queryKey: ["quotes", ...symbols],
    queryFn: () => api.quotes(symbols),
    enabled: symbols.length > 0,
    staleTime: STALE_TIME.quote,
    refetchInterval: (query: Query<QuoteResponse[]>) =>
      marketIsOpen(query.state.data?.[0]) ? BATCH_POLL_MS : false,
  });
}

export function useHistory(
  symbol: string | null,
  range = "1y",
  interval = "1d",
  opts?: { livePoll?: boolean }
) {
  // Shares the cache with any other `useQuote(symbol)` mounted elsewhere
  // (e.g. CompanyHeader) -- no extra network request just to read
  // market_status for the polling gate below.
  const { data: quote } = useQuote(opts?.livePoll ? symbol : null);
  return useQuery({
    queryKey: ["history", symbol, range, interval],
    queryFn: () => api.history(symbol as string, range, interval),
    enabled: !!symbol,
    staleTime: STALE_TIME.history,
    refetchInterval: opts?.livePoll ? () => (marketIsOpen(quote) ? BATCH_POLL_MS : false) : undefined,
  });
}

export function useFinancials(symbol: string | null, period: "annual" | "quarterly" = "annual") {
  return useQuery({
    queryKey: ["financials", symbol, period],
    queryFn: () => api.financials(symbol as string, period),
    enabled: !!symbol,
    staleTime: STALE_TIME.financials,
  });
}

export function useRatios(symbol: string | null) {
  return useQuery({
    queryKey: ["ratios", symbol],
    queryFn: () => api.ratios(symbol as string),
    enabled: !!symbol,
    staleTime: STALE_TIME.ratios,
  });
}

export function usePeers(symbol: string | null) {
  // Shares the cache with any other `useQuote(symbol)` mounted elsewhere
  // (e.g. CompanyHeader) -- React Query dedupes identical query keys, so
  // this never issues its own extra network request just to read
  // market_status for the polling gate below.
  const { data: quote } = useQuote(symbol);
  return useQuery({
    queryKey: ["peers", symbol],
    queryFn: () => api.peers(symbol as string),
    enabled: !!symbol,
    staleTime: STALE_TIME.peers,
    refetchInterval: () => (marketIsOpen(quote) ? BATCH_POLL_MS : false),
  });
}

export function useValuation(
  symbol: string | null,
  params?: { growthRatePct?: number; waccPct?: number; terminalGrowthPct?: number; forecastYears?: number }
) {
  return useQuery({
    queryKey: ["valuation", symbol, params ?? null],
    queryFn: () => api.valuation(symbol as string, params),
    enabled: !!symbol,
    staleTime: STALE_TIME.valuation,
  });
}

export function useOverview(symbol: string | null) {
  return useQuery({
    queryKey: ["overview", symbol],
    queryFn: () => api.overview(symbol as string),
    enabled: !!symbol,
    staleTime: STALE_TIME.valuation,
  });
}

export function useEvents(symbol: string | null) {
  return useQuery({
    queryKey: ["events", symbol],
    queryFn: () => api.events(symbol as string),
    enabled: !!symbol,
    staleTime: STALE_TIME.events,
  });
}

export function useKpiScorecard(symbol: string | null) {
  return useQuery({
    queryKey: ["kpi-scorecard", symbol],
    queryFn: () => api.kpiScorecard(symbol as string),
    enabled: !!symbol,
    staleTime: STALE_TIME.kpiScorecard,
  });
}

export function useGlossary() {
  return useQuery({
    queryKey: ["glossary"],
    queryFn: api.glossary,
    staleTime: STALE_TIME.glossary,
  });
}
