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


PeerBasis = Literal["sector", "template", "none"]


class RatioValue(BaseModel):
    value: float | None
    peer_median: float | None
    percentile: float | None


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


class EventsResponse(BaseModel):
    symbol: str
    dividends: list[DividendEvent]
    splits: list[SplitEvent]
    news: list[dict]
    source: str
    as_of: datetime
    warnings: list[str] = Field(default_factory=list)
