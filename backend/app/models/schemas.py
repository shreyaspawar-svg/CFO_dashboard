from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Template = Literal["bank", "nbfc", "insurance", "exchange", "general"]


class CompanyRef(BaseModel):
    symbol: str
    yf_ticker: str
    name: str
    template: Template


class SectorGroup(BaseModel):
    name: str
    companies: list[CompanyRef]


class UniverseResponse(BaseModel):
    sectors: list[SectorGroup]
    source: str = "backend/data/nifty50.json"
    as_of: datetime
    warnings: list[str] = Field(default_factory=list)


class QuoteResponse(BaseModel):
    symbol: str
    yf_ticker: str
    last_price: float | None = None
    change: float | None = None
    change_pct: float | None = None
    open: float | None = None
    day_high: float | None = None
    day_low: float | None = None
    prev_close: float | None = None
    volume: int | None = None
    week52_high: float | None = None
    week52_low: float | None = None
    market_cap: float | None = None
    market_status: Literal["open", "closed", "pre_open"] = "closed"
    source: str
    as_of: datetime
    warnings: list[str] = Field(default_factory=list)


class OHLCVBar(BaseModel):
    date: str
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    volume: int | None = None


class HistoryResponse(BaseModel):
    symbol: str
    range: str
    interval: str
    bars: list[OHLCVBar]
    benchmark_bars: list[OHLCVBar] = Field(default_factory=list)
    source: str
    as_of: datetime
    warnings: list[str] = Field(default_factory=list)


class FinancialPeriod(BaseModel):
    fiscal_year: str
    period_end: str
    line_items: dict[str, float | None]


class FinancialsResponse(BaseModel):
    symbol: str
    period: Literal["annual", "quarterly"]
    income_statement: list[FinancialPeriod]
    balance_sheet: list[FinancialPeriod]
    cash_flow: list[FinancialPeriod]
    source: str
    as_of: datetime
    warnings: list[str] = Field(default_factory=list)
    # Interpretation notes (e.g. "this ticker's older history predates a
    # demerger") -- distinct from `warnings`, which flags missing/absent
    # data. Never empty-vs-populated based on data completeness.
    notes: list[str] = Field(default_factory=list)
    # Structured form of the same corporate-action break (PLAN.md "Phase
    # 4.1 review" item 3): a chart needs an actual date and a short label,
    # not just a free-text note to parse. Both null when the symbol has no
    # recorded corporate action.
    comparable_from: str | None = None
    comparable_from_label: str | None = None


PeerBasis = Literal["sector", "template", "none"]


class RatioValue(BaseModel):
    value: float | None
    peer_median: float | None
    peer_min: float | None = None
    peer_max: float | None = None
    percentile: float | None
    # "computed" (our own calculation), "yahoo_fallback" (ours was None, a
    # crumb-gated Yahoo figure filled in -- a snapshot, not something a
    # history chart can replicate), or "unavailable". See PLAN.md "Phase 3
    # review" / Phase 2.2 item 3.
    method: Literal["computed", "yahoo_fallback", "unavailable"] = "unavailable"
    # Set when the value is real (non-None) but built on source data we've
    # positively detected as unreliable (e.g. HDFCBANK's equity-basis
    # oscillation, PLAN.md "Phase 4.1 review" item 1) -- the UI renders this
    # as an amber "source data inconsistent" badge with `data_quality_reason`
    # in a tooltip, rather than presenting the number as clean. `"ok"` (the
    # common case) means no such issue was detected.
    data_quality: Literal["ok", "inconsistent"] = "ok"
    data_quality_reason: str | None = None
    # Why `value` is None, when it is (PLAN.md "Phase 4.2 review"): "missing"
    # (an input was genuinely absent) vs "not_meaningful" (the inputs were
    # present but the computation isn't meaningful, e.g. growth from a
    # non-positive base) -- the UI shows "—" for the former, "n.m." for the
    # latter. `None` when `value` itself is real.
    reason: Literal["missing", "not_meaningful"] | None = None
    # Whether a higher or lower value is favourable (PLAN.md §4.3 item 2) --
    # the UI colours the percentile/direction badge accordingly, so a low
    # D/E renders as good, not bad. "neutral" for a figure with no inherent
    # good/bad direction (e.g. a DuPont structural component).
    direction: Literal["higher_better", "lower_better", "neutral"] = "higher_better"


class RatioHistoryPoint(BaseModel):
    fiscal_year: str
    period_end: str
    value: float | None


class Signal(BaseModel):
    type: Literal["strength", "watch"]
    rule: str
    message: str
    values: dict[str, float | None]


class AltmanZComponentOut(BaseModel):
    label: str
    value: float | None


class AltmanZDetailOut(BaseModel):
    score: float | None
    zone: Literal["safe", "grey", "distress"] | None
    components: list[AltmanZComponentOut]


class PiotroskiTestOut(BaseModel):
    label: str
    passed: bool | None


class PiotroskiDetailOut(BaseModel):
    earned: int
    possible: int
    tests: list[PiotroskiTestOut]


class QualityScores(BaseModel):
    altman: AltmanZDetailOut
    piotroski: PiotroskiDetailOut | None = None


class AxisComponent(BaseModel):
    metric: str
    value: float | None
    weight: float
    higher_is_better: bool
    percentile: float | None


class AxisResult(BaseModel):
    score: float | None
    components: list[AxisComponent]


class RatiosResponse(BaseModel):
    symbol: str
    template: Template
    peer_basis: PeerBasis
    peer_count: int
    comparable_annual_years: int
    growth_note: str | None = None
    ratios: dict[str, RatioValue]
    health_radar: dict[str, AxisResult]
    # Per-fiscal-year values for a ratio-card sparkline / the ratio-history
    # heatmap (PLAN.md §4.3 items 2/4). Spans every fetched period,
    # including any pre-comparable_from ones -- the UI marks the break
    # rather than excluding them, same convention as the price chart.
    history: dict[str, list[RatioHistoryPoint]] = Field(default_factory=dict)
    # "general" (3-step: margin x turnover x leverage) or "bank" (2-step:
    # ROA x leverage) -- PLAN.md §4.3 item 3. `None` only when no comparable
    # period was available to compute anything from.
    dupont_kind: Literal["general", "bank"] | None = None
    dupont_reconciliation_gap_pp: float | None = None
    signals: list[Signal] = Field(default_factory=list)
    # `None` for bank/NBFC/insurance templates -- Altman Z / Piotroski F
    # aren't meaningful without a current_assets/liabilities concept
    # (PLAN.md §4.3 item 6).
    quality_scores: QualityScores | None = None
    source: str
    as_of: datetime
    warnings: list[str] = Field(default_factory=list)


class PeerRow(BaseModel):
    symbol: str
    name: str
    template: Template
    last_price: float | None
    market_cap: float | None
    metrics: dict[str, float | None]


class PeersResponse(BaseModel):
    symbol: str
    peer_basis: PeerBasis
    peers: list[PeerRow]
    source: str
    as_of: datetime
    warnings: list[str] = Field(default_factory=list)


class ValuationResponse(BaseModel):
    symbol: str
    multiples: dict[str, float | None]
    dcf: dict[str, float | None]
    dcf_inputs: dict[str, float | None]
    reverse_dcf_implied_growth_pct: float | None
    source: str
    as_of: datetime
    warnings: list[str] = Field(default_factory=list)


class DividendEvent(BaseModel):
    date: str
    amount: float


class SplitEvent(BaseModel):
    date: str
    numerator: float
    denominator: float


class OverviewResponse(BaseModel):
    symbol: str
    beta: float | None = None
    analyst_target_mean: float | None = None
    analyst_target_high: float | None = None
    analyst_target_low: float | None = None
    analyst_count: float | None = None
    analyst_recommendation: str | None = None
    # 1-year total return, symbol minus benchmark/sector-peer-average, in
    # percentage points -- positive means the symbol outperformed.
    relative_performance_vs_nifty50_pp: float | None = None
    relative_performance_vs_sector_pp: float | None = None
    sector_peer_count: int = 0
    source: str
    as_of: datetime
    warnings: list[str] = Field(default_factory=list)


class EventsResponse(BaseModel):
    symbol: str
    dividends: list[DividendEvent]
    splits: list[SplitEvent]
    news: list[dict]
    source: str
    as_of: datetime
    warnings: list[str] = Field(default_factory=list)


class GlossaryEntry(BaseModel):
    label: str
    formula: str
    meaning: str
    good_looks_like: str


class GlossaryResponse(BaseModel):
    entries: dict[str, GlossaryEntry]
