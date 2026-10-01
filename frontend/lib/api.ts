import type { components } from "@/types/api";

// Empty by default: requests go to this same origin (e.g. "/api/universe"),
// which next.config.ts's rewrites forward server-side to the FastAPI
// backend. Only set NEXT_PUBLIC_API_BASE_URL if the frontend and backend
// are deployed on genuinely different origins with their own CORS setup.
const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";

export type UniverseResponse = components["schemas"]["UniverseResponse"];
export type QuoteResponse = components["schemas"]["QuoteResponse"];
export type HistoryResponse = components["schemas"]["HistoryResponse"];
export type FinancialsResponse = components["schemas"]["FinancialsResponse"];
export type RatiosResponse = components["schemas"]["RatiosResponse"];
export type RatioValue = components["schemas"]["RatioValue"];
export type AxisResult = components["schemas"]["AxisResult"];
export type PeersResponse = components["schemas"]["PeersResponse"];
export type ValuationResponse = components["schemas"]["ValuationResponse"];
export type EventsResponse = components["schemas"]["EventsResponse"];
export type OverviewResponse = components["schemas"]["OverviewResponse"];
export type CompanyRef = components["schemas"]["CompanyRef"];
export type SectorGroup = components["schemas"]["SectorGroup"];
export type GlossaryResponse = components["schemas"]["GlossaryResponse"];
export type GlossaryEntry = components["schemas"]["GlossaryEntry"];
export type RatioHistoryPoint = components["schemas"]["RatioHistoryPoint"];
export type Signal = components["schemas"]["Signal"];
export type PeerRow = components["schemas"]["PeerRow"];
export type QualityScores = components["schemas"]["QualityScores"];
export type BalanceSheetPeriodDetail = components["schemas"]["BalanceSheetPeriodDetail"];
export type CashFlowPeriodDetail = components["schemas"]["CashFlowPeriodDetail"];
export type CashFlowSankey = components["schemas"]["CashFlowSankey"];
export type KpiScorecardResponse = components["schemas"]["KpiScorecardResponse"];
export type KpiScorecardGroup = components["schemas"]["KpiScorecardGroup"];
export type KpiScorecardEntry = components["schemas"]["KpiScorecardEntry"];

class ApiError extends Error {
  constructor(
    public status: number,
    message: string
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function apiFetch<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`);
  if (!res.ok) {
    throw new ApiError(res.status, `${path} -> ${res.status}`);
  }
  return res.json() as Promise<T>;
}

// NIFTY symbols include "M&M" -- an un-encoded "&" in a query string splits
// it into two params, silently truncating `symbols` (real bug, caught while
// building the ticker tape: /api/quotes 404'd because the truncated list
// included a bare "M" that isn't a real symbol). Always encode.
export const api = {
  universe: () => apiFetch<UniverseResponse>("/api/universe"),
  quote: (symbol: string) => apiFetch<QuoteResponse>(`/api/quote/${encodeURIComponent(symbol)}`),
  quotes: (symbols: string[]) =>
    apiFetch<QuoteResponse[]>(
      `/api/quotes?symbols=${symbols.map(encodeURIComponent).join(",")}`
    ),
  history: (symbol: string, range = "1y", interval = "1d") =>
    apiFetch<HistoryResponse>(
      `/api/history/${encodeURIComponent(symbol)}?range=${range}&interval=${interval}`
    ),
  financials: (symbol: string, period: "annual" | "quarterly" = "annual") =>
    apiFetch<FinancialsResponse>(`/api/financials/${encodeURIComponent(symbol)}?period=${period}`),
  ratios: (symbol: string) => apiFetch<RatiosResponse>(`/api/ratios/${encodeURIComponent(symbol)}`),
  peers: (symbol: string) => apiFetch<PeersResponse>(`/api/peers/${encodeURIComponent(symbol)}`),
  valuation: (
    symbol: string,
    params?: { growthRatePct?: number; waccPct?: number; terminalGrowthPct?: number; forecastYears?: number }
  ) => {
    const query = new URLSearchParams();
    if (params?.growthRatePct != null) query.set("growth_rate_pct", String(params.growthRatePct));
    if (params?.waccPct != null) query.set("wacc_pct", String(params.waccPct));
    if (params?.terminalGrowthPct != null) query.set("terminal_growth_pct", String(params.terminalGrowthPct));
    if (params?.forecastYears != null) query.set("forecast_years", String(params.forecastYears));
    const qs = query.toString();
    return apiFetch<ValuationResponse>(`/api/valuation/${encodeURIComponent(symbol)}${qs ? `?${qs}` : ""}`);
  },
  events: (symbol: string) => apiFetch<EventsResponse>(`/api/events/${encodeURIComponent(symbol)}`),
  overview: (symbol: string) =>
    apiFetch<OverviewResponse>(`/api/overview/${encodeURIComponent(symbol)}`),
  glossary: () => apiFetch<GlossaryResponse>("/api/glossary"),
  kpiScorecard: (symbol: string) =>
    apiFetch<KpiScorecardResponse>(`/api/kpi-scorecard/${encodeURIComponent(symbol)}`),
};

export { ApiError };
