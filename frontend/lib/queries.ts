import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

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
} as const;

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
  });
}

export function useQuotes(symbols: string[]) {
  return useQuery({
    queryKey: ["quotes", ...symbols],
    queryFn: () => api.quotes(symbols),
    enabled: symbols.length > 0,
    staleTime: STALE_TIME.quote,
  });
}

export function useHistory(symbol: string | null, range = "1y", interval = "1d") {
  return useQuery({
    queryKey: ["history", symbol, range, interval],
    queryFn: () => api.history(symbol as string, range, interval),
    enabled: !!symbol,
    staleTime: STALE_TIME.history,
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
  return useQuery({
    queryKey: ["peers", symbol],
    queryFn: () => api.peers(symbol as string),
    enabled: !!symbol,
    staleTime: STALE_TIME.peers,
  });
}

export function useValuation(symbol: string | null) {
  return useQuery({
    queryKey: ["valuation", symbol],
    queryFn: () => api.valuation(symbol as string),
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

export function useGlossary() {
  return useQuery({
    queryKey: ["glossary"],
    queryFn: api.glossary,
    staleTime: STALE_TIME.glossary,
  });
}
