import statistics
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query

from app.config import get_settings
from app.metrics.dcf import (
    DEFAULT_FORECAST_YEARS,
    dcf_intrinsic_value,
    dcf_sensitivity_table,
    reverse_dcf_implied_growth,
)
from app.metrics.scoring import METRIC_HIGHER_IS_BETTER, percentile_rank
from app.metrics.valuation_bands import band_summary, compute_pe_pb_band, trailing_eps_series
from app.models.schemas import BandSummary, MultipleDetail, SensitivityTable, ValuationBandPoint, ValuationResponse
from app.services.balance_sheet import compute_balance_sheet_detail
from app.services.cache import get_cache
from app.services.datasource import get_data_source
from app.services.metrics_engine import compute_symbol_metrics
from app.services.normalize import clean_numeric, normalize_balance_sheet, normalize_income_statement
from app.services.peer_stats import compute_peer_metric_values
from app.services.universe import get_company

router = APIRouter(prefix="/api", tags=["valuation"])

MULTIPLE_KEYS = [
    "pe",
    "pb",
    "ev_ebitda",
    "ev_sales",
    "peg",
    "dividend_yield",
    "earnings_yield",
    "payout_ratio",
]

# A FCFF DCF assumes a "free cash flow to the firm" concept that doesn't
# hold for deposit-taking/underwriting businesses -- same set used for the
# balance sheet/cash flow tabs (PLAN.md §4.4/§4.5).
_DCF_NOT_APPLICABLE_TEMPLATES = ("bank", "nbfc", "insurance")

# DCF defaults, applied when the caller doesn't override them via query
# params. WACC/terminal growth are broad, documented assumptions for an
# Indian large-cap, not a per-company cost-of-capital estimate -- this is a
# what-if calculator, not a research desk output.
DEFAULT_WACC_PCT = 12.0
DEFAULT_TERMINAL_GROWTH_PCT = 4.0

_SENSITIVITY_WACC_STEPS_PCT = [-2.0, -1.0, 0.0, 1.0, 2.0]
_SENSITIVITY_TERMINAL_STEPS_PCT = [-1.0, -0.5, 0.0, 0.5, 1.0]


def _band_source_date(bar: dict) -> str:
    # History bars carry a full ISO datetime; band checkpoints only need the
    # date part to compare against period_end ("YYYY-MM-DD").
    return str(bar["date"])[:10]


async def _compute_pe_pb_band(company) -> list[dict]:
    # Independent of the DCF slider params, so it's cached by symbol alone
    # -- dragging a WACC/growth slider must never re-trigger a 5y price +
    # quarterly-statements fetch.
    cache = get_cache()
    settings = get_settings()
    cache_key = f"pe_pb_band:{company.symbol}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    data_source = get_data_source()
    try:
        price_records = await data_source.get_history_bars(company.yf_ticker, range_="5y", interval="1d")
    except Exception:  # noqa: BLE001
        price_records = []
    price_bars = [
        {"date": _band_source_date({"date": r.get("Date") or r.get("index")}), "close": clean_numeric(r.get("Close"))}
        for r in price_records
        if (r.get("Date") or r.get("index")) is not None
    ]
    if not price_bars:
        return []

    try:
        income_q_raw = await data_source.get_income_statement(company.yf_ticker, quarterly=True)
    except Exception:  # noqa: BLE001
        income_q_raw = []
    try:
        balance_q_raw = await data_source.get_balance_sheet(company.yf_ticker, quarterly=True)
    except Exception:  # noqa: BLE001
        balance_q_raw = []

    income_q = normalize_income_statement(income_q_raw)
    balance_q = normalize_balance_sheet(balance_q_raw)

    eps_points = [{"period_end": p["period_end"], "eps_diluted": p["line_items"].get("eps_diluted")} for p in income_q]
    trailing_eps_points = trailing_eps_series(eps_points)

    balance_detail_q = compute_balance_sheet_detail(balance_q, company.template)
    bvps_points = [{"period_end": p["period_end"], "bvps": p["bvps"]} for p in balance_detail_q]

    band = compute_pe_pb_band(price_bars, trailing_eps_points, bvps_points)
    cache.set(cache_key, band, settings.ttl_financials)
    return band


@router.get("/valuation/{symbol}", response_model=ValuationResponse)
async def get_valuation(
    symbol: str,
    growth_rate_pct: float | None = Query(None, description="Override the DCF's forecast growth rate (%)"),
    wacc_pct: float = Query(DEFAULT_WACC_PCT, description="Discount rate (%)"),
    terminal_growth_pct: float = Query(DEFAULT_TERMINAL_GROWTH_PCT, description="Terminal growth rate (%)"),
    forecast_years: int = Query(DEFAULT_FORECAST_YEARS, ge=1, le=15),
) -> ValuationResponse:
    company = get_company(symbol)
    if company is None:
        raise HTTPException(status_code=404, detail=f"Unknown symbol: {symbol}")

    settings = get_settings()
    cache = get_cache()
    is_default_request = (
        growth_rate_pct is None
        and wacc_pct == DEFAULT_WACC_PCT
        and terminal_growth_pct == DEFAULT_TERMINAL_GROWTH_PCT
        and forecast_years == DEFAULT_FORECAST_YEARS
    )
    cache_key = f"valuation:{company.symbol}"
    if is_default_request:
        cached = cache.get(cache_key)
        if cached is not None:
            return ValuationResponse(**cached)

    # Independent of the DCF slider params -- cached by symbol alone so a
    # slider drag doesn't re-fetch/re-derive the whole financials bundle.
    own_cache_key = f"own_metrics:{company.symbol}"
    result = cache.get(own_cache_key)
    if result is None:
        result = await compute_symbol_metrics(company.symbol)
        cache.set(own_cache_key, result, settings.ttl_financials)
    metrics = result["metrics"]
    latest_balance = result["latest_balance"]
    quote = result["quote"]

    multiples = {key: metrics.get(key) for key in MULTIPLE_KEYS}

    peer_data = await compute_peer_metric_values(company.symbol)
    peer_values = peer_data["peer_values"]
    multiples_detail: dict[str, MultipleDetail] = {}
    for key in MULTIPLE_KEYS:
        values_list = peer_values.get(key, [])
        valid_values = [v for v in values_list if v is not None]
        multiples_detail[key] = MultipleDetail(
            value=multiples[key],
            peer_median=statistics.median(valid_values) if valid_values else None,
            percentile=percentile_rank(multiples[key], values_list, METRIC_HIGHER_IS_BETTER.get(key, True)),
        )

    dcf_applicable = company.template not in _DCF_NOT_APPLICABLE_TEMPLATES

    base_fcff = metrics.get("fcf")
    total_debt = latest_balance.get("total_debt")
    cash = latest_balance.get("cash_and_equivalents")
    net_debt = (
        total_debt - (cash or 0) if total_debt is not None else None
    )
    price = quote.last_price
    market_cap = quote.market_cap
    shares_for_dcf = (
        market_cap / price if market_cap is not None and price not in (None, 0) else None
    )

    resolved_growth = growth_rate_pct if growth_rate_pct is not None else metrics.get("revenue_cagr_3y")

    warnings = list(result["warnings"])

    dcf: dict[str, float | None] = {"enterprise_value": None, "equity_value": None, "intrinsic_value_per_share": None}
    implied_growth = None
    sensitivity_table = None
    if dcf_applicable:
        dcf = dcf_intrinsic_value(
            base_fcff=base_fcff,
            growth_rate_pct=resolved_growth,
            wacc_pct=wacc_pct,
            terminal_growth_pct=terminal_growth_pct,
            net_debt=net_debt,
            shares_outstanding=shares_for_dcf,
            forecast_years=forecast_years,
        )
        implied_growth = reverse_dcf_implied_growth(
            base_fcff=base_fcff,
            current_price=price,
            wacc_pct=wacc_pct,
            terminal_growth_pct=terminal_growth_pct,
            net_debt=net_debt,
            shares_outstanding=shares_for_dcf,
            forecast_years=forecast_years,
        )
        sensitivity_table = SensitivityTable(
            **dcf_sensitivity_table(
                base_fcff=base_fcff,
                growth_rate_pct=resolved_growth,
                wacc_values_pct=[round(wacc_pct + d, 1) for d in _SENSITIVITY_WACC_STEPS_PCT],
                terminal_growth_values_pct=[round(terminal_growth_pct + d, 1) for d in _SENSITIVITY_TERMINAL_STEPS_PCT],
                net_debt=net_debt,
                shares_outstanding=shares_for_dcf,
                forecast_years=forecast_years,
            )
        )
        if resolved_growth is None:
            warnings.append("DCF growth rate unresolved (no override and no 3-yr revenue CAGR available)")
        if base_fcff is None:
            warnings.append("DCF unavailable: no free cash flow figure (reported or derived)")
    else:
        warnings.append(f"DCF not applicable for {company.template} template -- use P/B vs ROE instead")

    band = await _compute_pe_pb_band(company)
    pe_band = [ValuationBandPoint(date=b["date"], pe=b["pe"], pb=None) for b in band]
    pb_band = [ValuationBandPoint(date=b["date"], pe=None, pb=b["pb"]) for b in band]
    pe_summary = band_summary(band, "pe")
    pb_summary = band_summary(band, "pb")

    response = ValuationResponse(
        symbol=company.symbol,
        template=company.template,
        multiples=multiples,
        multiples_detail=multiples_detail,
        dcf=dcf,
        dcf_inputs={
            "base_fcff": base_fcff,
            "growth_rate_pct": resolved_growth,
            "wacc_pct": wacc_pct,
            "terminal_growth_pct": terminal_growth_pct,
            "forecast_years": float(forecast_years),
            "net_debt": net_debt,
            "shares_outstanding": shares_for_dcf,
        },
        dcf_applicable=dcf_applicable,
        sensitivity_table=sensitivity_table,
        reverse_dcf_implied_growth_pct=implied_growth,
        pe_band=pe_band,
        pb_band=pb_band,
        pe_band_summary=BandSummary(**pe_summary),
        pb_band_summary=BandSummary(**pb_summary),
        source="yahoo",
        as_of=datetime.now(timezone.utc),
        warnings=warnings,
    )
    if is_default_request:
        cache.set(cache_key, response.model_dump(mode="json"), settings.ttl_financials)
    return response
