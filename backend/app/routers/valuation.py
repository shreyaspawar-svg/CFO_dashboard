from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query

from app.config import get_settings
from app.metrics.dcf import DEFAULT_FORECAST_YEARS, dcf_intrinsic_value, reverse_dcf_implied_growth
from app.models.schemas import ValuationResponse
from app.services.cache import get_cache
from app.services.metrics_engine import compute_symbol_metrics
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

# DCF defaults, applied when the caller doesn't override them via query
# params. WACC/terminal growth are broad, documented assumptions for an
# Indian large-cap, not a per-company cost-of-capital estimate -- this is a
# what-if calculator, not a research desk output.
DEFAULT_WACC_PCT = 12.0
DEFAULT_TERMINAL_GROWTH_PCT = 4.0


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

    result = await compute_symbol_metrics(company.symbol)
    metrics = result["metrics"]
    latest_balance = result["latest_balance"]
    quote = result["quote"]

    multiples = {key: metrics.get(key) for key in MULTIPLE_KEYS}

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

    warnings = list(result["warnings"])
    if resolved_growth is None:
        warnings.append("DCF growth rate unresolved (no override and no 3-yr revenue CAGR available)")
    if base_fcff is None:
        warnings.append("DCF unavailable: no free cash flow figure (reported or derived)")

    response = ValuationResponse(
        symbol=company.symbol,
        multiples=multiples,
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
        reverse_dcf_implied_growth_pct=implied_growth,
        source="yahoo",
        as_of=datetime.now(timezone.utc),
        warnings=warnings,
    )
    if is_default_request:
        cache.set(cache_key, response.model_dump(mode="json"), settings.ttl_financials)
    return response
